"""
Sensor Adapters — Stubs for future input channels.

These define the interfaces for:
- Video input (camera, webcam, drone)
- Wearable data (smartwatch, health devices)
- Audio analysis (beyond transcription)

Implementation is hardware-dependent and deferred to Phase 3.
"""

from typing import Optional, Any, Protocol
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class SensorType(Enum):
    """Types of sensor inputs."""
    VIDEO = "video"
    WEARABLE = "wearable"
    AUDIO = "audio"


@dataclass
class SensorReading:
    """A reading from a sensor."""
    sensor_type: SensorType
    timestamp: datetime
    data: Any
    metadata: dict
    confidence: float = 1.0


class SensorAdapter(Protocol):
    """Protocol for sensor adapters."""
    
    def is_available(self) -> bool:
        """Check if sensor is available."""
        ...
    
    def read(self) -> Optional[SensorReading]:
        """Take a reading from the sensor."""
        ...
    
    def start_stream(self, callback) -> bool:
        """Start streaming readings to callback."""
        ...
    
    def stop_stream(self) -> bool:
        """Stop streaming."""
        ...


# --- Video Adapter Stub ---

@dataclass
class VideoFrame:
    """A video frame."""
    width: int
    height: int
    data: bytes  # Raw image data
    format: str = "rgb24"
    timestamp: Optional[datetime] = None


class VideoAdapter:
    """
    Stub for video input adapter.
    
    Future implementation will support:
    - Webcam capture
    - Phone camera
    - Drone feed
    - Body cam
    
    Use cases:
    - Injury assessment (show wound, get guidance)
    - Environmental hazard ID
    - Document/label reading
    - Plant/animal identification
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._streaming = False
    
    def is_available(self) -> bool:
        """Check if video capture is available."""
        # TODO: Check for camera hardware
        return False
    
    def capture_frame(self) -> Optional[VideoFrame]:
        """Capture a single frame."""
        raise NotImplementedError("Video capture not yet implemented")
    
    def read(self) -> Optional[SensorReading]:
        """Take a video reading (single frame analysis)."""
        frame = self.capture_frame()
        if not frame:
            return None
        
        return SensorReading(
            sensor_type=SensorType.VIDEO,
            timestamp=datetime.now(),
            data=frame,
            metadata={"width": frame.width, "height": frame.height}
        )
    
    def start_stream(self, callback) -> bool:
        """Start streaming video frames."""
        # TODO: Implement camera streaming
        return False
    
    def stop_stream(self) -> bool:
        """Stop streaming."""
        self._streaming = False
        return True
    
    def analyze_frame(self, frame: VideoFrame, analysis_type: str) -> dict:
        """
        Analyze a frame using vision model.
        
        Analysis types:
        - "describe": General description
        - "injury": Injury assessment
        - "hazard": Hazard identification
        - "text": OCR/text extraction
        - "identify": Object/entity identification
        
        TODO: Integrate with vision-capable LLM
        """
        raise NotImplementedError("Frame analysis not yet implemented")


# --- Wearable Adapter Stub ---

@dataclass
class WearableData:
    """Data from a wearable device."""
    heart_rate: Optional[int] = None  # BPM
    spo2: Optional[int] = None  # Oxygen saturation %
    temperature: Optional[float] = None  # Celsius
    steps: Optional[int] = None
    movement: Optional[str] = None  # "still", "walking", "running", "fallen"
    gps: Optional[tuple[float, float]] = None  # (lat, lon)
    battery: Optional[int] = None  # %


class WearableAdapter:
    """
    Stub for wearable device adapter.
    
    Future implementation will support:
    - Smartwatch (Apple Watch, Garmin, etc.)
    - Fitness bands
    - Medical devices (pulse oximeter, etc.)
    
    Use cases:
    - Health monitoring during emergency
    - Fall detection
    - Location tracking
    - Vital signs for medical guidance
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._connected = False
    
    def is_available(self) -> bool:
        """Check if wearable connection is available."""
        # TODO: Check for Bluetooth/connection
        return False
    
    def connect(self, device_id: Optional[str] = None) -> bool:
        """Connect to a wearable device."""
        # TODO: Implement Bluetooth pairing
        return False
    
    def disconnect(self) -> bool:
        """Disconnect from wearable."""
        self._connected = False
        return True
    
    def read(self) -> Optional[SensorReading]:
        """Take a wearable reading."""
        if not self._connected:
            return None
        
        # TODO: Read actual data from device
        data = WearableData()
        
        return SensorReading(
            sensor_type=SensorType.WEARABLE,
            timestamp=datetime.now(),
            data=data,
            metadata={"device": "unknown"}
        )
    
    def start_stream(self, callback, interval_seconds: int = 5) -> bool:
        """Start streaming readings at interval."""
        # TODO: Implement periodic reading
        return False
    
    def stop_stream(self) -> bool:
        """Stop streaming."""
        return True
    
    def check_alert_conditions(self, data: WearableData) -> list[str]:
        """
        Check for alert conditions in wearable data.
        
        Returns list of alerts (e.g., "low_spo2", "high_heart_rate", "fall_detected")
        
        TODO: Implement threshold checking
        """
        alerts = []
        
        if data.heart_rate and data.heart_rate > 150:
            alerts.append("high_heart_rate")
        
        if data.spo2 and data.spo2 < 90:
            alerts.append("low_spo2")
        
        if data.movement == "fallen":
            alerts.append("fall_detected")
        
        return alerts


# --- Audio Adapter Stub ---

@dataclass
class AudioSegment:
    """An audio segment."""
    duration_seconds: float
    sample_rate: int
    data: bytes
    format: str = "pcm16"


class AudioAdapter:
    """
    Stub for audio input adapter.
    
    This is for audio ANALYSIS beyond simple transcription.
    
    Use cases:
    - Ambient sound analysis (gunshots, explosions, alarms)
    - Distress detection in voice
    - Environmental monitoring
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._streaming = False
    
    def is_available(self) -> bool:
        """Check if audio capture is available."""
        # TODO: Check for microphone
        return False
    
    def capture(self, duration_seconds: float = 5.0) -> Optional[AudioSegment]:
        """Capture an audio segment."""
        raise NotImplementedError("Audio capture not yet implemented")
    
    def read(self) -> Optional[SensorReading]:
        """Take an audio reading."""
        segment = self.capture()
        if not segment:
            return None
        
        return SensorReading(
            sensor_type=SensorType.AUDIO,
            timestamp=datetime.now(),
            data=segment,
            metadata={"duration": segment.duration_seconds}
        )
    
    def start_stream(self, callback) -> bool:
        """Start streaming audio."""
        # TODO: Implement audio streaming
        return False
    
    def stop_stream(self) -> bool:
        """Stop streaming."""
        self._streaming = False
        return True
    
    def analyze(self, segment: AudioSegment, analysis_type: str) -> dict:
        """
        Analyze audio segment.
        
        Analysis types:
        - "transcribe": Speech to text
        - "classify": Sound classification
        - "emotion": Emotional analysis of speech
        - "alert": Alert sound detection
        
        TODO: Integrate with audio ML models
        """
        raise NotImplementedError("Audio analysis not yet implemented")
