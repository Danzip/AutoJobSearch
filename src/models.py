from enum import Enum


class JobStatus(str, Enum):
    FOUND = "found"
    ANALYZED = "analyzed"
    INTERESTING = "interesting"
    CV_GENERATED = "cv_generated"
    CONTACTED = "contacted"
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"
    SKIPPED = "skipped"


class JobSource(str, Enum):
    GREENHOUSE = "greenhouse"
    WORKABLE = "workable"
    WORKDAY = "workday"
    COMEET = "comeet"
    LINKEDIN = "linkedin"
    MANUAL = "manual"
    GENERIC = "generic"


CV_ANGLES = [
    "Edge AI / real-time deployment",
    "Production CV pipeline owner",
    "Object detection / perception",
    "Image registration / visual inspection",
    "Robotics / tracking / geometry",
    "General senior CV/DL engineer",
]

STATUS_FLOW = [s.value for s in JobStatus]
