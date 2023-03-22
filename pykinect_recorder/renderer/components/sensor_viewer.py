import os
import sys
import time
import datetime
import numpy as np
from pathlib import Path

from PySide6.QtCore import Qt, Slot, QEvent, QMimeData
from PySide6.QtGui import QImage, QPixmap, QDrag, QDragEnterEvent, QDragMoveEvent
from PySide6.QtWidgets import (
    QHBoxLayout, QPushButton, QVBoxLayout, 
    QFrame, QDialog, QGridLayout
)

from .custom_widgets import Label, Frame
from .viewer_sidebar import _config_sidebar
from .pyk4a_thread import Pyk4aThread
from .imu_viewer import IMUSensor
from .audio_viewer import AudioSensor
from pykinect_recorder.main.logger import logger
from pykinect_recorder.main._pyk4a.k4a._k4a import k4a_device_set_color_control
from pykinect_recorder.main._pyk4a.k4a.configuration import Configuration
from pykinect_recorder.main._pyk4a.pykinect import start_device, initialize_libraries


class SensorViewer(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(1200, 1000)
        self.setStyleSheet("background-color: black;") 
        self.device = None
        self.config = None
        self.color_control = None

        self.layout_grid = QGridLayout()
        self.frame_rgb = Frame("RGB Sensor")
        self.frame_depth = Frame("Depth Sensor")
        self.frame_ir = Frame("IR Sensor")
        
        self.layout_subdata = QHBoxLayout() # TODO => 네이밍 다시 하기
        self.imu_senser = IMUSensor()
        self.audio_sensor = AudioSensor()
        self.layout_subdata.addWidget(self.imu_senser)
        self.layout_subdata.addWidget(self.audio_sensor)
        self.frame_subdata = Frame("subdata", layout=self.layout_subdata)

        layout_btn = QHBoxLayout()
        self.btn_open = QPushButton("Device open")
        self.btn_viewer = QPushButton("▶")
        self.btn_record = QPushButton("●")

        self.btn_viewer.setStyleSheet("""
            QToolTip {
                font:"Arial"; font-size: 15px; color: #ffffff; border: 1px solid #ffffff; 
            }
            QPushButton {
                background-color: red;
            }
            """
        )
        self.btn_record.setStyleSheet("""
            QToolTip {
                font:"Arial"; font-size: 15px; color: #ffffff; border: 1px solid #ffffff; 
            }
            """
        )

        self.btn_viewer.setToolTip("<b>Streaming Button</b>")
        self.btn_record.setToolTip("<b>Recording Button</b>")
        
        layout_btn.addWidget(self.btn_open)
        layout_btn.addWidget(self.btn_viewer)
        layout_btn.addWidget(self.btn_record)
        
        self.th = Pyk4aThread(device=self.device)
        self.th.RGBUpdateFrame.connect(self.setRGBImage)
        self.th.DepthUpdateFrame.connect(self.setDepthImage)
        self.th.IRUpdateFrame.connect(self.setIRImage)
            
        self.is_device = True
        self.is_viewer = True
        self.is_record = True
        self.btn_open.clicked.connect(self.open_device)
        self.btn_viewer.clicked.connect(self.streaming)
        self.btn_record.clicked.connect(self.recording)
        
        self.layout_grid.addWidget(self.frame_rgb, 0, 0)
        self.layout_grid.addWidget(self.frame_depth, 0, 1)
        self.layout_grid.addWidget(self.frame_ir, 1, 0)
        self.layout_grid.addWidget(self.frame_subdata, 1, 1)
        self.layout_grid.addLayout(layout_btn, 2, 0, 1, 2)

        self.setLayout(self.layout_grid)
        
    def check_device(self) -> bool:
        try:
            self.config = Configuration()

            for k, v in _config_sidebar.items():
                setattr(self.config, k, v)

            initialize_libraries()
            _device = start_device(config=self.config)
            logger.debug(
                "카메라 연결에 문제에 이상이 없습니다."
            )
            _device.close()
        except:
            modal = QDialog()
            layout_modal = QVBoxLayout()
            e_message = Label(
                "<b>카메라 연결에 문제가 있습니다. <br> 연결을 재시도해주세요.</b>", 
                "Arial", 20, Qt.AlignmentFlag.AlignCenter
            )
            logger.error(
                "카메라 연결에 문제가 있습니다. 연결을 재시도해주세요"
            )

            layout_modal.addWidget(e_message)
            modal.setLayout(layout_modal)
            modal.setWindowTitle("Error Message")
            modal.resize(400, 200)
            modal.exec()
            sys.exit(0)

    def open_device(self) -> None:
        if self.is_device is True:
            self.check_device()
            self.is_device = False
            self.btn_open.setText("Device close")
        else:
            self.frame_rgb.frame.setText("RGB Frame")
            self.frame_depth.frame.setText("Depth Frame")
            self.frame_ir.frame.setText("IR Frame")
            self.is_device = True
            self.btn_open.setText("Device open")
            self.device = None
    
    # TODO Streaming 이랑 Recording 겹치는 코드가 많음.
    def streaming(self) -> None:
        if self.is_viewer:
            self.device = start_device(config=self.config, record=False)
            self.th.device = self.device

            self.btn_record.setEnabled(False)
            self.th.is_run = True
            self.btn_viewer.setText("■")
            self.is_viewer = False
            self.th.start()
        else:
            self.btn_record.setEnabled(True)
            self.th.is_run = False
            self.btn_viewer.setText("▶")
            self.is_viewer = True
            self.device.close()
            self.th.quit()
            time.sleep(1)   
        
    def recording(self) -> None:
        if self.is_record:
            self.set_filename()
            self.device = start_device(
                config=self.config, 
                record=True, 
                record_filepath=self.filename_video
            )
            self.th.device = self.device

            self.btn_viewer.setEnabled(False)
            self.th.is_run = True
            self.btn_record.setText("■")
            self.is_record = False
            self.th.start()
        else:
            self.btn_viewer.setEnabled(True)
            self.th.is_run = False
            self.btn_record.setText("▶")
            self.is_record = True
            self.device.close()
            self.th.quit()
            time.sleep(1)

    def set_filename(self) -> None:
        base_path = os.path.join(Path.home(), "Videos")

        filename = datetime.datetime.now()
        filename = filename.strftime("%Y_%m_%d_%H_%M_%S")

        self.filename_video = os.path.join(base_path, f"{filename}.mkv")
        # self.filename_audio = os.path.join(base_path, f"{filename}.wav")
        if sys.flags.debug:
            print(base_path, self.filename_video)
        
    @Slot(QImage)
    def setRGBImage(self, image: QImage) -> None:
        self.frame_rgb.frame.setPixmap(QPixmap.fromImage(image))
    
    @Slot(QImage)
    def setDepthImage(self, image: QImage) -> None:
        self.frame_depth.frame.setPixmap(QPixmap.fromImage(image))
        
    @Slot(QImage)
    def setIRImage(self, image: QImage) -> None:
        self.frame_ir.frame.setPixmap(QPixmap.fromImage(image))
        
    def initial_check(self) -> bool:
        # TODO: pykinect_recorder 폴더에서 유틸로 처리
        # self.logger
        initial_flag = True
        logger.debug("---------------녹화 시작 전 테스트를 진행합니다.---------------")
        logger.debug(
            f"\n \
            FPS : {str(self.azure_device._config.camera_fps)}\n \
            color_format: {str(self.azure_device._config.color_format)}\n \
            color_resolution: {str(self.azure_device._config.color_resolution)}\n \
            depth_mode: {str(self.azure_device._config.depth_mode)}"
        )
        self.logger.debug("\n---------------영상 테스트를 시작합니다.---------------")

        try:
            self.azure_device.start()
            num_frames = 0

            while num_frames < 10:
                frame = self.azure_device.get_capture()
                if frame.color.shape[2] != 4:
                    self.logger.debug("RGBD 영상의 차원이 올바르지 않습니다.")
                    initial_flag = False
                if not np.any(frame.depth):
                    self.logger.debug("Depth 영상을 찾을 수 없습니다.")
                    initial_flag = False

                num_frames += 1
            self.azure_device.close()

        except Exception as e:
            self.logger.debug(e)

        finally:
            self.logger.debug("카메라 연결 테스트를 종료합니다.")
            return initial_flag