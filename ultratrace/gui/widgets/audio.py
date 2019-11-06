import utils

from . import OptionalWidget

class Audio(OptionalWidget):
    def __init__(self, app, args):
        super().__init__(app)

        if not args.audio:
            return

        try:
            import pyaudio
            from pydub import AudioSegment
            self.is_imported = True
        except ImportError:
            utils.warn('Audio Widget failed to load')
            return
