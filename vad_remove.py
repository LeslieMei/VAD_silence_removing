import os
import argparse
import glob
from tqdm import tqdm
import webrtcvad
import collections
import contextlib
import wave


'''Parse input arguments'''

parser = argparse.ArgumentParser(description="remove silence")
parser.add_argument('--data_path', type=str, default='', help='Data directory')
parser.add_argument('--save_path', type=str, default='data', help='Save path')
parser.add_argument('--vad_mode', type=int, default=0, help='aggresiveness mode between 0 and 3')
parser.add_argument('--frame_duration', type=int, default=20, help='frame duration between 10, 20 and 30')
args = parser.parse_args()

def read_wav(path):
    """
    Reads a wav file
    returns (PCM audio data, sample date)
    """
    
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        num_channels = wf.getnchannels()
        assert num_channels == 1
        sample_width = wf.getsampwidth()
        assert sample_width == 2
        sample_rate = wf.getframerate()
        assert sample_rate in (8000, 16000, 32000, 48000)
        pcm_data = wf.readframes(wf.getnframes())
        return pcm_data, sample_rate
    
def write_wav(path, audio, sample_rate):
    """
    writes a wav file
    """
    
    with contextlib.closing(wave.open(path, 'wb')) as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio)

class Frame(object):
    """
    Represent a 'frame' of audio data
    """
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration
        
def frame_generator(frame_duration_ms, audio, sample_rate):
    """
    Generate audio frames from PCM audio data
    """
    
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / sample_rate) / 2.0
    while offset + n < len(audio):
        yield Frame(audio[offset: offset + n], timestamp, duration)
        timestamp += duration
        offset += n
        
def vad_collector(sample_rate, frame_duration_ms,
                 padding_duration_ms, vad, frames):
    """
    Filters out non_voiced frames
    """
    
    num_padding_frames = int(padding_duration_ms / frame_duration_ms)
    ring_buffer = collections.deque(maxlen=num_padding_frames)
    triggered = False
    
    voiced_frames = []
    for frame in frames:
        is_speech = vad.is_speech(frame.bytes, sample_rate)
        
        if not triggered:
            ring_buffer.append((frame, is_speech))
            num_voiced = len([f for f, speech in ring_buffer if speech])
            if num_voiced > 0.9 * ring_buffer.maxlen:
                triggered = True
                for f, s in ring_buffer:
                    voiced_frames.append(f)
                ring_buffer.clear()
        else:
            if num_voiced > 0.9 * ring_buffer.maxlen:
                triggered = False
                yield b''.join([f.bytes for f in voiced_frames])
                ring_buffer.clear()
                voiced_frames = []
    if voiced_frames:
        yield b''.join([f.bytes for f in voiced_frames])
            
                    
    
    
def make_dirs(args):
    
    folders = glob.glob('%s/*/*'%args.data_path)
    folders.sort()
    
    save_folder = args.save_path
    save_folder = save_folder.strip()
    save_folder = save_folder.rstrip("/")
    
    for folder in folders:
        folder = folder.split('/')[-2] + ('/') + folder.split('/')[-1]
        path = save_folder + '/' + folder
        
        isExists = os.path.exists(path)
        if not isExists:
            os.makedirs(path)
            #print("make dir for %s"%path)
        #else:
            #print("%s already exists"%path)
        
    print("save folders created successfully")


def remove_silence(args):

    wav_files = glob.glob('%s/*/*/*.wav'%args.data_path)
    wav_files.sort()
    frame_duration = args.frame_duration
    vad_mode = args.vad_mode
    save_folder = args.save_path
    save_folder = save_folder.strip()
    save_folder = save_folder.rstrip("/")
    x = 1
    
    for fname in tqdm(wav_files):
        audio, sample_rate = read_wav(fname)
        spk_folder = fname.split('/')[-3]
        utter_folder = fname.split('/')[-2]
        wav_name = fname.split('/')[-1].rstrip('.wav')
        vad = webrtcvad.Vad(vad_mode)
        frames = frame_generator(frame_duration, audio, sample_rate)
        frames = list(frames)
        segments = vad_collector(sample_rate, frame_duration, 300, vad, frames)
        for i, segment in enumerate(segments):
            path = save_folder + '/' + spk_folder + '/' + utter_folder + '/' + wav_name + 'chunk-' + str(i) + '.wav'
            write_wav(path, segment, sample_rate)
            x = x + 1
        chunk_files = save_folder + '/' + spk_folder + '/' + utter_folder + '/' + wav_name + 'chunk-'
        chunk_files = glob.glob('%s*.wav'%chunk_files)
        nframes = b''
        for chunk_file in chunk_files:
            with contextlib.closing(wave.open(chunk_file, 'rb')) as wf:
                params = wf.getparams()
                nframes += wf.readframes(params[3]) 
        wav_name = save_folder + '/' + spk_folder + '/' + utter_folder + '/' + wav_name + '.wav'
        with contextlib.closing(wave.open(wav_name, 'wb')) as wf:
            wf.setnchannels(params[0])
            wf.setsampwidth(params[1])
            wf.setframerate(params[2])
            wf.writeframes(nframes)
        for chunk_file in chunk_files:
            os.remove(chunk_file)
    print("Finished, %d wav files  are processed"%x)
            
if __name__ == "__main__":
    
    print("Making directories...")
    make_dirs(args)
    print("removeing silence")
    remove_silence(args)
    orign_len = 0
    orign_files = glob.glob('%s/*/*/*.wav'%args.data_path)
    for orign_file in orign_files:
        with contextlib.closing(wave.open(orign_file, 'rb')) as wf:
            orign_len += wf.getnframes()
    modified_files = glob.glob('%s/*/*/*.wav'%args.save_path)
    modified_len = 0
    for modified_file in modified_files:
        with contextlib.closing(wave.open(modified_file, 'rb')) as wf:
            modified_len += wf.getnframes()    
    print('Orignal duration for all wav files %d s'%(orign_len/16000))
    print('Modified duration for all wav files %d s'%(modified_len/16000))
