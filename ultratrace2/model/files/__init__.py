import logging

from .registry import register_loader_for_extensions_and_mime_types as __register


logger = logging.getLogger(__name__)


try:
    from .loaders import DICOMLoader

    __register(
        [".dicom", ".dcm"], ["application/dicom"], DICOMLoader,
    )
except ImportError as e:
    logger.warning(e)

try:
    from .loaders import FLACLoader

    __register(
        [], [], FLACLoader,
    )
except ImportError as e:
    logger.warning(e)

try:
    from .loaders import MeasurementLoader

    __register(
        [], [], MeasurementLoader,
    )
except ImportError as e:
    logger.warning(e)

try:
    from .loaders import MP3Loader

    __register(
        [], [], MP3Loader,
    )
except ImportError as e:
    logger.warning(e)

try:
    from .loaders import OggLoader

    __register(
        [], [], OggLoader,
    )
except ImportError as e:
    logger.warning(e)

try:
    from .loaders import TextGridLoader

    __register(
        [".textgrid"], ["text/plain"], TextGridLoader,
    )
except ImportError as e:
    logger.warning(e)

try:
    from .loaders import WAVLoader

    __register(
        [".wav"], ["audio/x-wav", "audio/wav"], WAVLoader,
    )
except ImportError as e:
    logger.warning(e)
