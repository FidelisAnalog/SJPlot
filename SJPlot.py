'''
PLEASE READ

DO NOT EDIT THIS SCRIPT!

Configuration is now stored in a separate file with the default name "SJPlot.cfg"  This file should be in
the same directory that this script is run from.

You can also pass the configuration via the command line: "python sjplot.py --help" for syntax.

Details in the README here: https://sjplot.com
'''


from scipy.signal import sosfiltfilt, iirfilter, lfilter, resample, hilbert, butter
from scipy.ndimage import uniform_filter1d
from scipy.io.wavfile import read, write
from matplotlib.legend_handler import HandlerBase
from matplotlib.offsetbox import AnchoredText
from itertools import chain
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import FuncFormatter
import numpy as np
import os
import logging
import argparse
import configparser
import io


__version__ = "18.5.1"


# Try to import js module for web environment
try:
    from js import document, console
    _IS_WEB_ENV = True
except ImportError:
    _IS_WEB_ENV = False


class WebStatusHandler(logging.Handler):
    """Custom logging handler for web environment that updates UI status."""
    def emit(self, record):
        if not _IS_WEB_ENV:
            return
        
        try:
            # Get just the message text (everything after level name)
            msg = self.format(record)
            # Extract message after "INFO - " or "DEBUG - " etc
            if ' - ' in msg:
                status_text = msg.split(' - ', 2)[-1]  # Get everything after second dash
            else:
                status_text = msg
            
            # Call JavaScript function to update UI (works across worker boundary)
            try:
                from js import window
                if hasattr(window, 'updateProgressStatus'):
                    window.updateProgressStatus(status_text)
            except Exception as inner_e:
                console.error(f"Error calling updateProgressStatus: {inner_e}")
                
            # Log message to console
            console.log(msg)
        except Exception as e:
            if _IS_WEB_ENV:
                console.error(f"WebStatusHandler error: {e}")
                import traceback
                console.error(traceback.format_exc())


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)
logger.propagate = False

# Set up handler based on environment (at module load time)
if _IS_WEB_ENV:
    # We're in web mode - use WebStatusHandler
    web_handler = WebStatusHandler()
    web_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    web_handler.setFormatter(web_formatter)
    logger.addHandler(web_handler)
else:
    # We're in standalone mode - use StreamHandler
    stream_handler = logging.StreamHandler()
    stream_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)

def get_environment():
    """
    Detect the runtime environment.
    Returns:
        'web' if running in a PyScript environment.
        'standalone' if running in a standard Python environment.
    """
    try:
        import pyscript  # PyScript module is only available in the web environment
        logger.info(f"Running from PyScript")
        return 'web'
    except ImportError:
        logger.info(f"Running Standalone")
        return 'standalone'


def get_config():
    # Default configuration file name
    default_config_file = "SJPlot.cfg"

    # Argument parser setup
    parser = argparse.ArgumentParser(description="Process parameters for SJPlot.")
    parser.add_argument("--config", default=default_config_file, type=str, help="Path to configuration file.", metavar ="")
    parser.add_argument("--file_0", type=str, help="Path to the first input WAV file.", metavar ="")
    parser.add_argument("--file_1", type=str, help="Path to the second input WAV file.", metavar ="")
    parser.add_argument("--extract_sweeps", default=None, action="store_true", help="Extract sweeps from first input file.")
    parser.add_argument("--save_sweeps", default=None, action="store_true", help="Save extracted sweep files.")
    parser.add_argument("--test_record", type=str, help="Test record for extracting sweeps.")
    parser.add_argument("--plot_info", type=str, help="See README for more information.", metavar ="")
    parser.add_argument("--equip_info", type=str, help="See README for more information.", metavar ="")
    parser.add_argument("--author", type=str, help="See README for more information.", metavar ="")
    parser.add_argument("--plot_style", type=int, choices=[1, 2, 3, 4, 5], help="The plot style to output.")
    parser.add_argument("--plot_data_out", default=None, action="store_true", help="Output plot data.")
    parser.add_argument("--round_level", type=int, help="{integer} Rounding level.", metavar ="")
    parser.add_argument("--riaa_mode", type=int, choices=[0, 1, 2, 3], help="0 = none, 1 = bass, 2 = treble, 3 = both.")
    parser.add_argument("--riaa_inverse", default=None, action="store_true", help="Invert RIAA filter(s).")
    parser.add_argument("--str100", default=None, action="store_true", help="Apply STR100 correction.")
    parser.add_argument("--xg7001", default=None, action="store_true", help="Apply XG7001 correction.")
    parser.add_argument("--normalize", type=int, help="{integer} Frequency in Hz to normalize at.", metavar = "")
    parser.add_argument("--file0norm", default=None, action="store_true", help="Normalize both files to file_0.")
    parser.add_argument("--start_f", type=int, help="{integer} Start frequency in Hz.", metavar = "")
    parser.add_argument("--end_f", type=int, help="{integer} End frequency in Hz.", metavar = "")
    parser.add_argument("--override_y_limit_value", nargs=2, type=int, help="Override Y limit values as two integers, ex: {-10 10}", metavar = "{int}")
    parser.add_argument('--version', action='version', version='SJPlot ' + __version__)
    parser.add_argument("--log_level", default=None, type=str, choices=['info', 'debug'], help="Change console logging level to DEBUG.")


    # Parse command-line arguments
    args = vars(parser.parse_args())


    # Load configuration from INI file
    config_file = args.get("config", default_config_file)
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)
    else:
        logger.info(f"No configuration file. Using default values.")
    
    # Set default values for missing parameters
    defaults = {
        "file_0": "",
        "file_1": "",
        "extract_sweeps": False,
        "save_sweeps": False,
        "test_record": "",
        "plot_info": "Cart / Load / Record",
        "equip_info": "Arm -> Phonostage -> ADC",
        "author": "",
        "plot_style": 4,
        "plot_data_out": False,
        "round_level": 1,
        "riaa_mode": 2,
        "riaa_inverse": True,
        "str100": False,
        "xg7001": False,
        "normalize": 1000,
        "file0norm": False,
        "start_f": "",
        "end_f": "",
        "override_y_limit": False,
        "override_y_limit_value": [-0, 0],
        "log_level": "info",
    }

    # Start with defaults
    combined_config = {**defaults}


    # Apply INI configuration (if present)
    for section in config.sections():
        for key, value in config.items(section):
            if key in combined_config:
                # Convert types to match defaults
                if isinstance(defaults[key], bool):
                    combined_config[key] = config.getboolean(section, key)
                elif isinstance(defaults[key], int):
                    combined_config[key] = config.getint(section, key)
                elif isinstance(defaults[key], list):
                    combined_config[key] = [int(i) for i in value.split(",")]
                else:
                    combined_config[key] = value

    # Check for web configuration (from index.html via PyScript)
    try:
        from js import window
        if hasattr(window, 'js_config'):
            web_config = window.js_config.to_py()  # Convert JsProxy to Python dict
            logger.info("Applying web configuration overrides.")
            logger.info(f"Web config received: {web_config}")
            for key, value in web_config.items():
                if key in combined_config:
                    combined_config[key] = value
                    logger.info(f"Applied config: {key} = {value}")
    except ImportError:
        # Not running in a PyScript environment, continue as standalone
        pass


    # Apply command-line arguments, giving precedence to command-line input
    for key, value in args.items():
        if value is not None:  # Only apply non-None values
            combined_config[key] = value
  
    # Automatically set override_y_limit to 1 if override_y_limit_value is provided
    if combined_config["override_y_limit_value"] != defaults["override_y_limit_value"]:
        combined_config["override_y_limit"] = 1

    # Automatically set str100 to 1 if test_record = str100 is provided
    if combined_config["test_record"].casefold() == "str100".casefold():
        combined_config["str100"] = 1

    # Automatically set xg7001 to 1 if test_record = xg7001 is provided
    if combined_config["test_record"].casefold() == "xg7001".casefold():
        combined_config["xg7001"] = 1


    return combined_config


# Write Output WAV File
def write_file(file, data, Fs):
    write(file, Fs, data)

def align_yaxis(ax1, ax2):
    y_lims = np.array([ax.get_ylim() for ax in [ax1, ax2]])

    # force 0 to appear on both axes, comment if don't need
    y_lims[:, 0] = y_lims[:, 0].clip(None, 0)
    y_lims[:, 1] = y_lims[:, 1].clip(0, None)

    # normalize both axes
    y_mags = (y_lims[:,1] - y_lims[:,0]).reshape(len(y_lims),1)
    y_lims_normalized = y_lims / y_mags

    # find combined range
    y_new_lims_normalized = np.array([np.min(y_lims_normalized), np.max(y_lims_normalized)])

    # denormalize combined range to get new axes
    new_lim1, new_lim2 = y_new_lims_normalized * y_mags
    return new_lim1, new_lim2


class AnyObjectHandler(HandlerBase):
    def create_artists(self, legend, orig_handle,
                       x0, y0, width, height, fontsize, trans):

        l1 = plt.Line2D([x0,y0+width], [0.7*height,0.7*height],
                           color=orig_handle[0], linestyle=orig_handle[1])

        l2 = plt.Line2D([x0,y0+width], [0.3*height,0.3*height],
                           color=orig_handle[2], linestyle=orig_handle[3])
        return [l1, l2]
 

def ft_window(n):
    a0, a1, a2, a3, a4 = 0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368
    x = np.arange(n)
    w = (a0 - a1*np.cos(2*np.pi*x/(n-1)) + a2*np.cos(4*np.pi*x/(n-1)) - 
         a3*np.cos(6*np.pi*x/(n-1)) + a4*np.cos(8*np.pi*x/(n-1)))
    return w


def find_nearest(array, value):
    """Fast version for sorted arrays using binary search."""
    idx = np.searchsorted(array, value)
    
    # Handle edge cases
    if idx == 0:
        return 0
    if idx == len(array):
        return len(array) - 1
    
    # Check which is actually closer: idx or idx-1
    if abs(array[idx] - value) < abs(array[idx-1] - value):
        return idx
    else:
        return idx - 1



def createplotdata(signal, Fs, iteration=[0], norm=[0], start_f=None, end_f=20000, str100=0, file0norm=0, normalize=1000):

    def interpolate(f, a, minf, maxf, fstep):
        # Ensure inputs are NumPy arrays
        f, a = np.array(f), np.array(a)

        bins = np.arange(minf, maxf + fstep, fstep)  # Define bin edges
        indices = np.digitize(f, bins) - 1  # Find the bin index for each frequency
        f_out, a_out = [], []
        
        for i, bin_center in enumerate(bins):
            mask = (indices == i)
            if np.any(mask):
                f_out.append(bin_center)
                a_out.append(20 * np.log10(np.mean(a[mask])))

        return f_out, a_out

 
    def rfft(signal, Fs, minf, maxf, fstep):

        freq, amp, freqx, ampx, freq2h, amp2h, freq3h, amp3h = [], [], [], [], [], [], [], []

        F = int(Fs/fstep)
        win = ft_window(F)

        if len(signal.shape) == 1: # mono signal
            signal = np.expand_dims(signal, axis=0)
            
        for x in range(0, signal.shape[1] - F,F):

            y0 = abs(np.fft.rfft(signal[0, x:x + F] * win))
            f0 = np.argmax(y0) #use largest bin
            if f0 >=minf/fstep and f0 <=maxf/fstep:
                freq.append(f0*fstep)
                amp.append(y0[f0])
            if 2*f0<F/2-2 and f0 > minf/fstep and f0 < maxf/fstep:
                f2 = np.argmax(y0[(2*f0)-2:(2*f0)+2])
                freq2h.append(f0*fstep)
                amp2h.append(y0[2*f0-2+f2])
            if 3*f0<F/2-2 and f0 > minf/fstep and f0 < maxf/fstep:
                f3 = np.argmax(y0[(3*f0)-2:(3*f0)+2])
                freq3h.append(f0*fstep)
                amp3h.append(y0[3*f0-2+f3])

            if signal.shape[0] > 1: # Process second channel if stereo
                y1 = abs(np.fft.rfft(signal[1, x:x + F] * win))
                f1 = np.argmax(y1) #use largest bin
                if f0 >=minf/fstep and f0 <=maxf/fstep: # use primary sweep f range
                    freqx.append(f1*fstep)
                    ampx.append(y1[f1])
            else:
                ampx = 0  # No secondary channel for mono
                freqx = 0

        return freq, amp, freqx, ampx, freq2h, amp2h, freq3h, amp3h


    def normstr100(f, a):
        fmin = 40
        fmax = 500
        slope = -6.02
        for x in range(find_nearest(f, fmin), (find_nearest(f, fmax))):
            a[x] = a[x] + 20*np.log10(1*((f[x])/fmax)**((slope/20)/np.log10(2)))
        return a


    def process_chunk(signal, Fs, fmin, fmax, step, offset):
            f, a, fx, ax, f2, a2, f3, a3 = rfft(signal, Fs, fmin, fmax, step)
            
            f, a = interpolate(f, a, fmin, fmax, step)
            fx, ax = interpolate(fx, ax, fmin, fmax, step)
            f2, a2 = interpolate(f2, a2, fmin, fmax, step)
            f3, a3 = interpolate(f3, a3, fmin, fmax, step)
            
            a = [amp - offset for amp in a]
            ax = [amp - offset for amp in ax] if ax else []
            a2 = [amp - offset for amp in a2]
            a3 = [amp - offset for amp in a3]
            return f, a, fx, ax, f2, a2, f3, a3
            
            
            
            
    def slice_frequency_range(freq_array, amp_array, start_f=None, end_f=None):
	    # Handle start
        if not start_f:  # Catches None, "", 0, etc.
            idx_min = 0
        else:
            idx_min = find_nearest(freq_array, float(start_f))
		
	    # Handle end
        if not end_f:
            idx_max = len(freq_array) - 1
        else:
            idx_max = find_nearest(freq_array, float(end_f))
		
	    # Ensure proper order
        if idx_min > idx_max:
            idx_min, idx_max = idx_max, idx_min

        return freq_array[idx_min:idx_max+1], amp_array[idx_min:idx_max+1]


    fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = [], [], [], [], [], [], [], []
    
    for fmin, fmax, step, offset in [(20,45,5,26.03), (50,90,10,19.995), (100,980,20,13.99), (1000,50000,100,0)]:
        f, a, fx, ax, f2, a2, f3, a3 = process_chunk(signal, Fs, fmin, fmax, step, offset)
        fout.extend(f); aout.extend(a); foutx.extend(fx); aoutx.extend(ax)
        fout2.extend(f2); aout2.extend(a2); fout3.extend(f3); aout3.extend(a3)


    if str100 == 1:
        aout = normstr100(fout, aout)
        aout2 = normstr100(fout2, aout2)
        aout3 = normstr100(fout3, aout3)
        if aoutx:
            aoutx = normstr100(foutx, aoutx)

    if file0norm == 0 and iteration[0] == 0:
        i = find_nearest(fout, normalize)
        norm[0] = aout[i]
    elif file0norm == 1:
        i = find_nearest(fout, normalize)
        norm[0] = aout[i]
 
    aout = [a - norm[0] for a in aout]
    aoutx = [a - norm[0] for a in aoutx] if aoutx else []
    aout2 = [a - norm[0] for a in aout2]
    aout3 = [a - norm[0] for a in aout3]

    # Apply low-pass filter
    sos = iirfilter(3, 0.5, btype='lowpass', output='sos')  # Low-pass filter
    aout = sosfiltfilt(sos, aout)
    aout2 = sosfiltfilt(sos, aout2)
    aout3 = sosfiltfilt(sos, aout3)
    if len(aoutx) > 0:
        aoutx = sosfiltfilt(sos, aoutx)

    iteration[0]+=1
    
    # Slice frequency range if start_f and end_f are provided
    fout, aout = slice_frequency_range(fout, aout, start_f, end_f)
    foutx, aoutx = slice_frequency_range(foutx, aoutx, start_f, end_f)
    fout2, aout2 = slice_frequency_range(fout2, aout2, start_f, end_f)
    fout3, aout3 = slice_frequency_range(fout3, aout3, start_f, end_f)
    

    return fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3


def ordersignal(signal, Fs):
    F = int(Fs/100)
    win = ft_window(F)

    if len(signal.shape) == 1: # if mono signal
        signal = np.expand_dims(signal, axis=0)

    y = abs(np.fft.rfft(signal[0,0:F]*win))
    minf = np.argmax(y)
    y = abs(np.fft.rfft(signal[0][len(signal[0])-F:len(signal[0])]*win))
    maxf = np.argmax(y)
                      
    if maxf < minf:
        maxf,minf = minf,maxf
        signal = np.flipud(signal)
 
    return signal, minf, maxf


def riaaiir(sig, Fs, mode, inv):
    if Fs == 96000:
        at = [1, -0.66168391, -0.18158841]
        bt = [0.1254979638905360, 0.0458786797031512, 0.0018820452752401]
        ars = [1, -0.60450091, -0.39094593]
        brs = [0.90861261463964900, -0.52293147388301200, -0.34491369168550900]
    if inv == 1:
        at,bt = bt,at
        ars,brs = brs,ars
    if mode == 1:
        sig = lfilter(brs,ars,sig)
    if mode == 2:
        sig = lfilter(bt,at,sig)
    if mode == 3:
        sig = lfilter(bt,at,sig)
        sig = lfilter(brs,ars,sig)
    return sig


def normxg7001(signal, Fs):
    if Fs == 96000:
        b = [1.0080900, -0.9917285, 0]
        a = [1, -0.9998364, 0]
        signal = lfilter(b,a,signal)
    return signal


def get_audio(input_data, environment='standalone', extract_sweeps=0, test_record=None, save_sweeps=0, riaa_mode=0, riaa_inverse=False, xg7001=False):

    if environment == 'web':
        if not input_data:
            raise ValueError("No input data provided for web environment")
        try:
            size = input_data.getbuffer().nbytes
        except AttributeError:
            size = len(input_data) if input_data else 0
        logger.info(f"Reading input for web environment ({size} bytes)")
        with io.BytesIO(input_data) as wav_io:
            # Suppress WAV file warnings about non-data chunks (metadata)
            import warnings
            from scipy.io.wavfile import WavFileWarning
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=WavFileWarning)
                Fs, audio = read(wav_io)
    else:
        logger.info(f"Reading input from file path: {input_data}")
        # Suppress WAV file warnings about non-data chunks (metadata)
        import warnings
        from scipy.io.wavfile import WavFileWarning
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=WavFileWarning)
            Fs, audio = read(input_data)

    logger.info(f"Sample Rate: {Fs}")

    if Fs <96000:
        logger.info(f"Resampling to 96000")
        audio = resample(audio, int(len(audio) * 96000 / Fs))
        Fs = 96000

    if extract_sweeps == 1:
        logger.info(f"Extracting sweeps from audio file...")
        audio, audio_2 = slice_audio(audio, Fs, test_record)

        if save_sweeps == 1:

            output_file_left = os.path.splitext(input_data)[0] + '_L.wav'
            output_file_right = os.path.splitext(input_data)[0] + '_R.wav'

            logger.info(f"Writing {output_file_left}")
            write_file(output_file_left, audio, Fs)

            logger.info(f"Writing {output_file_right}")
            write_file(output_file_right, audio_2, Fs)  
        
        audio = audio.T
        audio_2 = audio_2.T
    else:
        audio = audio.T

    if riaa_mode != 0:
        audio = riaaiir(audio, Fs, riaa_mode, riaa_inverse)
        try:
            audio_2 = riaaiir(audio_2, Fs, riaa_mode, riaa_inverse)
        except NameError:
            audio_2 = None
    elif extract_sweeps != 1:
        audio_2 = None

    if xg7001 == 1:
        audio = normxg7001(audio, Fs)
        try:
            audio_2 = normxg7001(audio_2, Fs)
            #print('norm 0')
        except NameError:
            audio_2 = None
            #print('norm 1')
    elif extract_sweeps != 1:
        audio_2 = None


    audio, minf, maxf = ordersignal(audio, Fs)
    
    logger.info(f"Raw sweep from {minf * 100:.0f}Hz to {maxf * 100:.0f}Hz")
    #logger.info(f"Raw sweep maximum frequency: {maxf * 100:.0f}Hz")
 
    return audio, audio_2, Fs


def slice_audio(signal, Fs, test_record):

    def find_burst_bounds(signal, Fs, tone_freq=1000, min_duration=1.0, threshold=0.3, search_duration=30.0):
        """
        Find pilot tone burst using Hilbert envelope method.
        More robust and sample-rate independent than peak-spacing method.
        
        Parameters:
        - signal: input audio signal
        - Fs: sample rate
        - tone_freq: expected pilot tone frequency (default 1000 Hz)
        - min_duration: minimum duration in seconds for valid burst (default 1.0s)
        - threshold: normalized envelope threshold (default 0.3 = 30% of peak)
        - search_duration: duration to search in seconds (default 30s)
        
        Returns:
        - start_sample: sample index where burst starts
        - end_sample: sample index where burst ends
        """
        # Only process first search_duration seconds to keep processing fast
        search_samples = int(search_duration * Fs)
        if len(signal) > search_samples:
            logger.debug(f"Limiting search to first {search_duration}s ({search_samples} samples)")
            signal_search = signal[:search_samples]
        else:
            signal_search = signal
        
        # Bandpass filter around tone frequency (±50 Hz tolerance)
        sos = butter(4, [tone_freq - 50, tone_freq + 50], btype='band', fs=Fs, output='sos')
        filtered = sosfiltfilt(sos, signal_search)
        
        # Hilbert transform to get analytic signal and envelope
        analytic_signal = hilbert(filtered)
        envelope = np.abs(analytic_signal)
        
        # Fast envelope smoothing using uniform_filter1d
        window_size = int(0.1 * Fs)
        envelope_smooth = uniform_filter1d(envelope, size=window_size, mode='nearest')
        
        # Normalize envelope
        envelope_norm = envelope_smooth / np.max(envelope_smooth)
        
        # Threshold detection
        above_threshold = envelope_norm > threshold
        
        # Find transitions (rising and falling edges)
        transitions = np.diff(above_threshold.astype(int))
        starts = np.where(transitions == 1)[0]
        ends = np.where(transitions == -1)[0]
        
        # Find first sustained region above threshold
        min_samples = int(min_duration * Fs)
        
        for start, end in zip(starts, ends):
            duration = end - start
            if duration >= min_samples:
                logger.debug(f"Found burst: start={start}, end={end}, duration={duration/Fs:.2f}s")
                
                return start, end
        
        raise ValueError(f"No sustained pilot tone found in first {search_duration}s (min duration: {min_duration}s, threshold: {threshold})")


    def find_sweep_start(signal, Fs, search_duration=10.0, threshold=0.2):
        """
        Find the start of a frequency sweep (rising energy), not a sustained tone.
        Used for test records where sweep starts several seconds after pilot tone ends.
        
        Parameters:
        - signal: raw audio signal
        - Fs: sample rate  
        - search_duration: how long to search (seconds)
        - threshold: energy rise threshold (default 0.2 = 20% of max)
        
        Returns:
        - start_sample: where sweep energy begins to rise
        """
        search_samples = int(search_duration * Fs)
        if len(signal) > search_samples:
            signal_search = signal[:search_samples]
        else:
            signal_search = signal
        
        # Bandpass around 1kHz (sweep typically starts at 1kHz)
        sos = butter(4, [900, 1100], btype='band', fs=Fs, output='sos')
        filtered = sosfiltfilt(sos, signal_search)
        
        # Get envelope
        envelope = np.abs(hilbert(filtered))
        
        # Smooth with larger window to see overall energy trend
        window_size = int(0.2 * Fs)  # 200ms window
        envelope_smooth = uniform_filter1d(envelope, size=window_size, mode='nearest')
        
        # Normalize
        envelope_norm = envelope_smooth / np.max(envelope_smooth)
        
        # Find where energy rises above threshold
        above_threshold = envelope_norm > threshold
        
        # Find first rising edge
        transitions = np.diff(above_threshold.astype(int))
        rises = np.where(transitions == 1)[0]
        
        if len(rises) > 0:
            start_sample = rises[0]
            logger.debug(f"Found sweep start at sample {start_sample} ({start_sample/Fs:.2f}s)")
            
            return start_sample
        else:
            raise ValueError(f"No sweep start found in first {search_duration}s")



    def find_end_of_sweep(sweep_start_sample, sweep_end_min, sweep_end_max, signal, Fs, threshold=0.05):
        """
        Find end of frequency sweep using Hilbert envelope - optimized and automatic.
        Works for sweeps ending anywhere from 10kHz to 75kHz without configuration.
        
        Parameters:
        - sweep_start_sample: sample where sweep starts
        - sweep_end_min: minimum expected sweep duration (seconds)
        - sweep_end_max: maximum expected sweep duration (seconds)
        - signal: raw audio signal (not pre-filtered)
        - Fs: sample rate
        - threshold: relative amplitude threshold for end detection (default 0.05 = 5%)
        
        Returns:
        - end_sample: sample index where sweep ends
        """
        # Define search window
        sample_offset_start = sweep_start_sample + int(Fs * sweep_end_min)
        sample_offset_end = sweep_start_sample + int(Fs * sweep_end_max)
        signal_window = signal[sample_offset_start:sample_offset_end]
        
        logger.debug(f"End search window: {len(signal_window)} samples ({len(signal_window)/Fs:.2f}s)")
        
        # Use a moderate highpass (5kHz) to catch energy from sweeps ending anywhere 10kHz-75kHz
        # This is well below even the lowest sweep end, so it will catch the drop
        highpass_freq = min(5000, Fs * 0.4)  # 5kHz or 40% of Nyquist, whichever is lower
        sos = butter(4, highpass_freq, btype='high', fs=Fs, output='sos')
        filtered = sosfiltfilt(sos, signal_window)
        
        # Hilbert envelope - much cleaner than rectification
        envelope = np.abs(hilbert(filtered))
        
        # Fast smoothing with smaller window for better time resolution
        window_size = int(0.01 * Fs)  # 10ms window
        envelope_smooth = uniform_filter1d(envelope, size=window_size, mode='nearest')
        
        # Normalize
        envelope_norm = envelope_smooth / np.max(envelope_smooth)
        
        # Find where envelope drops below threshold
        below_threshold = envelope_norm < threshold
        
        # Find first sustained drop (to avoid false triggers on transients)
        min_samples = int(0.05 * Fs)  # Must stay below for 50ms
        
        # Fast vectorized method using diff to find transitions
        if len(below_threshold) >= min_samples:
            # Find transitions in/out of low region
            padded = np.concatenate(([False], below_threshold, [False]))
            diff = np.diff(padded.astype(int))
            starts = np.where(diff == 1)[0]  # Start of low regions
            ends = np.where(diff == -1)[0]   # End of low regions
            
            # Find first region that's >= min_samples long
            if len(starts) > 0 and len(ends) > 0:
                durations = ends - starts
                long_enough = np.where(durations >= min_samples)[0]
                
                if len(long_enough) > 0:
                    end_sample = sample_offset_start + starts[long_enough[0]]
                else:
                    # No sustained region, use first drop
                    end_sample = sample_offset_start + starts[0]
            else:
                # No low regions at all
                end_sample = sample_offset_end
        else:
            # Window too small, use midpoint
            end_sample = (sample_offset_start + sample_offset_end) // 2
        
        logger.debug(f"End Sample (Global Index): {end_sample}")
        
        return end_sample

    # Test record parameters
    record_params = {
        'TRS1007': {'sweep_offset': 78, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
        'TRS1005': {'sweep_offset': 32, 'sweep_end_min': 26, 'sweep_end_max': 34, 'sweep_start_detect': 1},
        'STR100': {'sweep_offset': 74, 'sweep_end_min': 64, 'sweep_end_max': 66, 'sweep_start_detect': 0},
        'STR120': {'sweep_offset': 56, 'sweep_end_min': 45, 'sweep_end_max': 50, 'sweep_start_detect': 0},
        'STR130': {'sweep_offset': 80, 'sweep_end_min': 63, 'sweep_end_max': 67, 'sweep_start_detect': 0},
        'STR170': {'sweep_offset': 72, 'sweep_end_min': 63, 'sweep_end_max': 67, 'sweep_start_detect': 0},
        'QR2009': {'sweep_offset': 78, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
        'QR2010': {'sweep_offset': 22, 'sweep_end_min': 15, 'sweep_end_max': 18, 'sweep_start_detect': 0},
        'XG7001': {'sweep_offset': 78, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
        'XG7002': {'sweep_offset': 63, 'sweep_end_min': 26, 'sweep_end_max': 30, 'sweep_start_detect': 1},
        'XG7005': {'sweep_offset': 76, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
	    'DIN45543': {'sweep_offset': 78, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
	    'ИЗМ33С0327': {'sweep_offset': 58, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
    }

    if test_record.upper() not in record_params:
        raise ValueError("Invalid test record.")

    params = record_params[test_record.upper()]

    left = signal[:, 0]
    right = signal[:, 1]

    logger.info(f"Test Record: {test_record}")

    # Find end of left pilot tone / start of sweep using Hilbert method
    # Note: find_burst_bounds_hilbert does its own filtering
    _, start_left_sweep = find_burst_bounds(left, Fs, tone_freq=1000, threshold=0.3)

    if params['sweep_start_detect'] == 1:
        # For test records where sweep starts several seconds after pilot ends
        # Look for energy rise at 1kHz (sweep start), not another sustained tone
        sample_offset = start_left_sweep + Fs  # Start searching 1s after pilot ends
        start_left_sweep = sample_offset + find_sweep_start(left[sample_offset:], Fs, search_duration=10.0, threshold=0.2)

    logger.info(f"Start of Left Sweep: {start_left_sweep}")

    # Find end of right pilot tone / start of sweep
    sample_offset = start_left_sweep + int(Fs * params['sweep_offset'])
    _, start_right_sweep = sample_offset + find_burst_bounds(right[sample_offset:], Fs, tone_freq=1000, threshold=0.3)

    if params['sweep_start_detect'] == 1:
        # Same for right channel
        sample_offset = start_right_sweep + Fs
        start_right_sweep = sample_offset + find_sweep_start(right[sample_offset:], Fs, search_duration=10.0, threshold=0.2)

    logger.info(f"Start of Right Sweep: {start_right_sweep}")

    # Find end of left sweep using Hilbert method
    # Automatically detects end for sweeps ending 10kHz-75kHz
    end_left_sweep = find_end_of_sweep(
        start_left_sweep, 
        params['sweep_end_min'], 
        params['sweep_end_max'], 
        left,
        Fs
    )
    logger.info(f"End of Left Sweep: {end_left_sweep}")

    # Find end of right sweep
    end_right_sweep = find_end_of_sweep(
        start_right_sweep, 
        params['sweep_end_min'], 
        params['sweep_end_max'], 
        right,
        Fs
    )
    logger.info(f"End of Right Sweep: {end_right_sweep}")

    logger.info(f"Left Sweep Duration: {(end_left_sweep-start_left_sweep)/Fs:.4f}")
    logger.info(f"Right Sweep Duration: {(end_right_sweep-start_right_sweep)/Fs:.4f}")

    left_slice = np.column_stack((left[start_left_sweep:end_left_sweep], right[start_left_sweep:end_left_sweep]))
    right_slice = np.column_stack((right[start_right_sweep:end_right_sweep], left[start_right_sweep:end_right_sweep]))

    logger.info(f"Sweep extraction completed.")

    return left_slice, right_slice

def format_freq(x, pos):
    """Format frequency values with k notation for tick labels"""
    if x == 0:
        return '0'
    elif x >= 1000:
        # Format with k suffix, remove trailing zeros and decimal point
        return f'{x/1000:.10g}k'.rstrip('0').rstrip('.')
    else:
        return f'{x:.10g}'


def _generate_csv_string(fo, ao, aox, ao2h, ao3h):
    """
    Helper function to generate CSV string from plot data arrays.

    Args:
        fo: Frequency data
        ao: Amplitude data
        aox: Crosstalk data
        ao2h: 2nd harmonic data
        ao3h: 3rd harmonic data

    Returns:
        CSV formatted string
    """
    import csv
    from io import StringIO

    # Pad arrays to match frequency array length
    dao = [*ao, *[''] * (len(fo) - len(ao))]
    daox = [*aox, *[''] * (len(fo) - len(aox))]
    dao2h = [*ao2h, *[''] * (len(fo) - len(ao2h))]
    dao3h = [*ao3h, *[''] * (len(fo) - len(ao3h))]

    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(['Frequency', 'Amplitude', 'Crosstalk', '2nd Harmonic', '3rd Harmonic'])

    for f, a, ax, a2, a3 in zip(fo, dao, daox, dao2h, dao3h):
        # Round numeric values to 2 decimals, preserve empty strings
        f_out = round(f, 2) if f != '' else ''
        a_out = round(a, 2) if a != '' else ''
        ax_out = round(ax, 2) if ax != '' else ''
        a2_out = round(a2, 2) if a2 != '' else ''
        a3_out = round(a3, 2) if a3 != '' else ''
        writer.writerow([f_out, a_out, ax_out, a2_out, a3_out])

    csv_data = csv_buffer.getvalue()
    csv_buffer.close()

    return csv_data


def output_plot_data(fo0, ao0, aox0, ao2h0, ao3h0, fo1=None, ao1=None, aox1=None, ao2h1=None, ao3h1=None,
                     environment='standalone', filename_base='plot_data'):
    """
    Output plot data to CSV file or prepare for web frontend.

    Args:
        fo0: Frequency data for file 0
        ao0: Amplitude data for file 0
        aox0: Crosstalk data for file 0
        ao2h0: 2nd harmonic data for file 0
        ao3h0: 3rd harmonic data for file 0
        fo1: Frequency data for file 1 (optional)
        ao1: Amplitude data for file 1 (optional)
        aox1: Crosstalk data for file 1 (optional)
        ao2h1: 2nd harmonic data for file 1 (optional)
        ao3h1: 3rd harmonic data for file 1 (optional)
        environment: 'standalone' or 'web'
        filename_base: Base name for output CSV file
    """
    # Generate CSV data for file 0
    csv_data0 = _generate_csv_string(fo0, ao0, aox0, ao2h0, ao3h0)

    # Generate CSV data for file 1 if present
    csv_data1 = None
    if fo1 is not None and ao1 is not None:
        csv_data1 = _generate_csv_string(fo1, ao1, aox1, ao2h1, ao3h1)

    if environment == 'standalone':
        if csv_data1:
            # Dual file output - use L/R suffixes
            csv_file_L = f"{filename_base}_L.csv"
            with open(csv_file_L, 'w') as f:
                f.write(csv_data0)
            logger.info(f"Left channel plot data written to {csv_file_L}")

            csv_file_R = f"{filename_base}_R.csv"
            with open(csv_file_R, 'w') as f:
                f.write(csv_data1)
            logger.info(f"Right channel plot data written to {csv_file_R}")
        else:
            # Single file output - no suffix needed
            csv_file = f"{filename_base}.csv"
            with open(csv_file, 'w') as f:
                f.write(csv_data0)
            logger.info(f"Plot data written to {csv_file}")

    elif environment == 'web':
        # Send CSV data to JS frontend
        from js import window

        if hasattr(window, 'updateUIWithPlotData'):
            window.updateUIWithPlotData(csv_data0, csv_data1)
            logger.info("Plot data sent to web frontend")
        else:
            logger.warning("updateUIWithPlotData function not found in JS window object")


def main():
    """
    Main entry point for SJPlot analysis.
    Can be called from standalone mode or web environment.
    """

    createplotdata.__defaults__ = ([0], [0], 0, 20000, 0, 0, 1000)

    config = get_config()

    INPUT_FILE_0 = config["file_0"]
    INPUT_FILE_1 = config["file_1"]
    EXTRACT_SWEEPS = config["extract_sweeps"]
    SAVE_SWEEPS = config["save_sweeps"]
    TEST_RECORD = config["test_record"]
    PLOT_INFO = config["plot_info"]
    EQUIP_INFO = config["equip_info"]
    AUTHOR = config["author"]
    PLOT_STYLE = config["plot_style"]
    PLOT_DATA_OUT = config["plot_data_out"]
    ROUND_LEVEL = config["round_level"]
    RIAA_MODE = config["riaa_mode"]
    RIAA_INVERSE = config["riaa_inverse"]
    STR100 = config["str100"]
    XG7001 = config["xg7001"]
    NORMALIZE = config["normalize"]
    FILE0NORM = config["file0norm"]
    START_F = config["start_f"]
    END_F = config["end_f"]
    OVERRIDE_Y_LIMIT = config["override_y_limit"]
    OVERRIDE_Y_LIMIT_VALUE = config["override_y_limit_value"]
    LOG_LEVEL = config["log_level"]

    if LOG_LEVEL.upper() == 'DEBUG':
        logger.setLevel(level=logging.DEBUG)
    if LOG_LEVEL.upper() == 'INFO':
        logger.setLevel(level=logging.INFO)



    if logging.getLogger(__name__).isEnabledFor(logging.DEBUG):
        logger.debug(f"Configuration Parameters:")
        for key, value in config.items():
            logger.debug(f"  {key}: {value}")



    logger.info(f"SJPlot {__version__}")

    environment = get_environment()

    # Get file data based on environment with memory optimization
    if environment == 'web':
        from js import window
        # File 0 - More efficient data conversion with memory management
        file0_array = window.js_file0_data.to_py()
        file0_data = bytes(file0_array)
        del file0_array  # Free memory immediately
        
        # File 1 (if present)
        if window.js_file1_data:
            file1_array = window.js_file1_data.to_py()
            file1_data = bytes(file1_array)
            del file1_array  # Free memory immediately
        else:
            file1_data = None
    else:
        file0_data = INPUT_FILE_0
        file1_data = INPUT_FILE_1


    if EXTRACT_SWEEPS == 1:
        input_sig_0, input_sig_1, Fs = get_audio(file0_data, environment, EXTRACT_SWEEPS, TEST_RECORD, SAVE_SWEEPS, RIAA_MODE, RIAA_INVERSE, XG7001)

        fo0, ao0, fox0, aox0, fo2h0, ao2h0, fo3h0, ao3h0 = createplotdata(input_sig_0, Fs, start_f=START_F, end_f=END_F, str100=STR100, file0norm=FILE0NORM, normalize=NORMALIZE)

        deltaadj = ao0[find_nearest(fo0, NORMALIZE)]
        deltah0 = round((max(ao0 - deltaadj)), ROUND_LEVEL)
        deltal0 = abs(round((min(ao0 - deltaadj)), ROUND_LEVEL))

        logger.info(f"Left crosstalk @1kHz: {aox0[find_nearest(fox0, 1000)]:.2f}dB")

        fo1, ao1, fox1, aox1, fo2h1, ao2h1, fo3h1, ao3h1 = createplotdata(input_sig_1, Fs, start_f=START_F, end_f=END_F, str100=STR100, file0norm=FILE0NORM, normalize=NORMALIZE)
 
        deltaadj = ao1[find_nearest(fo1, NORMALIZE)]
        deltah1 = round((max(ao1 - deltaadj)), ROUND_LEVEL)
        deltal1 = abs(round((min(ao1 - deltaadj)), ROUND_LEVEL))

        logger.info(f"Right crosstalk @1kHz: {aox1[find_nearest(fox1, 1000)]:.2f}dB")

        file1_data = '_'


    else:
        input_sig, _, Fs = get_audio(file0_data, environment, riaa_mode=RIAA_MODE, riaa_inverse=RIAA_INVERSE, xg7001=XG7001)
        fo0, ao0, fox0, aox0, fo2h0, ao2h0, fo3h0, ao3h0 = createplotdata(input_sig, Fs, start_f=START_F, end_f=END_F, str100=STR100, file0norm=FILE0NORM, normalize=NORMALIZE)

        deltaadj = ao0[find_nearest(fo0, NORMALIZE)]
        deltah0 = round((max(ao0 - deltaadj)), ROUND_LEVEL)
        deltal0 = abs(round((min(ao0 - deltaadj)), ROUND_LEVEL))

        if len(aox0) > 0:
            logger.info(f"Left crosstalk @1kHz: {aox0[find_nearest(fox0, 1000)]:.2f}dB")


        if file1_data:
            input_sig, _, Fs = get_audio(file1_data, environment, riaa_mode=RIAA_MODE, riaa_inverse=RIAA_INVERSE, xg7001=XG7001)
            fo1, ao1, fox1, aox1, fo2h1, ao2h1, fo3h1, ao3h1 = createplotdata(input_sig, Fs, start_f=START_F, end_f=END_F, str100=STR100, file0norm=FILE0NORM, normalize=NORMALIZE)
     
            deltaadj = ao1[find_nearest(fo1, NORMALIZE)]
            deltah1 = round((max(ao1 - deltaadj)), ROUND_LEVEL)
            deltal1 = abs(round((min(ao1 - deltaadj)), ROUND_LEVEL))

            if len(aox1) > 0:
                logger.info(f"Right crosstalk @1kHz: {aox1[find_nearest(fox1, 1000)]:.2f}dB")


    if PLOT_DATA_OUT == 1:
        # Output plot data based on environment
        plot_filename_base = PLOT_INFO.replace(' / ', '_')
        if file1_data:
            output_plot_data(fo0, ao0, aox0, ao2h0, ao3h0,
                           fo1=fo1, ao1=ao1, aox1=aox1, ao2h1=ao2h1, ao3h1=ao3h1,
                           environment=environment, filename_base=plot_filename_base)
        else:
            output_plot_data(fo0, ao0, aox0, ao2h0, ao3h0,
                           environment=environment, filename_base=plot_filename_base)


    plt.rcParams["xtick.minor.visible"] =  True
    plt.rcParams["ytick.minor.visible"] =  True

    if PLOT_STYLE == 1:
        fig, axs = plt.subplots(1, 1, figsize=(14,6))
        axs = np.ravel([axs])

        axs[0].semilogx(fo0,ao0, color = '#0000ff', label = 'Freq Response')

        axs[0].semilogx(fo2h0,ao2h0,color = '#0080ff', label = '2ⁿᵈ Harmonic', alpha = 1, linewidth = 0.75)
        axs[0].semilogx(fo3h0,ao3h0,color = '#00dfff', label = '3ʳᵈ Harmonic', alpha = 1, linewidth = 0.75)

        axs[0].semilogx(fox0,aox0,color = '#0000ff', linestyle = (0, (3, 1, 1, 1)), label = 'Crosstalk')
 

        if file1_data:
            axs[0].semilogx(fo1,ao1, color = '#ff0000', label = 'Freq Response')

            axs[0].semilogx(fo2h1,ao2h1,color = '#ff8000', label = '2ⁿᵈ Harmonic', alpha = 1, linewidth = 0.75)
            axs[0].semilogx(fo3h1,ao3h1,color = '#ffdf00', label = '3ʳᵈ Harmonic', alpha = 1, linewidth = 0.75)

            axs[0].semilogx(fox1,aox1,color = '#ff0000', linestyle = (0, (3, 1, 1, 1)), label = 'Crosstalk')

            plt.legend([("#0000ff", "-", "#ff0000", "-"), ("#0000ff", (0, (3, 1, 1, 1)), "#ff0000", (0, (3, 1, 1, 1))),
                        ("#0080ff", "-", "#ff8000", "-"), ("#00dfff", "-", "#ffdf00", "-")],
                       ['Freq Response', 'Crosstalk', '2ⁿᵈ Harmonic', '3ʳᵈ Harmonic'],
                       handler_map={tuple: AnyObjectHandler()},loc=4)

            axs[0].set_ylim((min(chain(aox0, aox1)) -2), (max(chain(ao0, ao1)) +2))

        else:   
            plt.legend(loc=4)

        axs[0].set_ylabel("Amplitude (dB)")
        axs[0].set_xlabel("Frequency (Hz)")

        plt.autoscale(enable=True, axis='y')

        if OVERRIDE_Y_LIMIT == 1:
            axs[0].set_ylim(*OVERRIDE_Y_LIMIT_VALUE)
 

    if PLOT_STYLE == 2:
        fig, axs = plt.subplots(1, sharex=True, figsize=(14,6))
        axs = np.ravel([axs])
        axtwin = axs[0].twinx()

        axs[0].set_ylim(-5,5)


        if max(ao0) <7:
            axs[0].set_ylim(-25, 7)

        if max(ao0) < 4:
            axs[0].set_ylim(-25,5)
     
        if max(ao0) < 2:
            axs[0].set_ylim(-29,3)

        if max(ao0) < 0.5:
            axs[0].set_ylim(-30,2)


        if len(aox0) > 0:
            if INPUT_FILE_1:
                axs[0].set_ylim((min(chain(aox0, aox1)) -2), (max(chain(ao0, ao1)) +2))
            else:
                axs[0].set_ylim((min(aox0) -2), (max(ao0) +2))
 
        if OVERRIDE_Y_LIMIT == 1:
            axs[0].set_ylim(*OVERRIDE_Y_LIMIT)

 
        axs[0].semilogx(fo0,ao0, color = '#0000ff', label = 'Freq Response')

        axtwin.semilogx(fo2h0,ao2h0,color = '#0080ff', label = '2ⁿᵈ Harmonic', alpha = 1, linewidth = 0.75)
        axtwin.semilogx(fo3h0,ao3h0,color = '#00dfff', label = '3ʳᵈ Harmonic', alpha = 1, linewidth = 0.75)

        axs[0].semilogx(fox0,aox0,color = '#0000ff', linestyle = (0, (3, 1, 1, 1)), label = 'Crosstalk')
 
 
        if file1_data:
            axs[0].semilogx(fo1,ao1, color = '#ff0000', label = 'Freq Response')

            axtwin.semilogx(fo2h1,ao2h1,color = '#ff8000', label = '2ⁿᵈ Harmonic', alpha = 1, linewidth = 0.75)
            axtwin.semilogx(fo3h1,ao3h1,color = '#ffdf00', label = '3ʳᵈ Harmonic', alpha = 1, linewidth = 0.75)

            axs[0].semilogx(fox1,aox1,color = '#ff0000', linestyle = (0, (3, 1, 1, 1)), label = 'Crosstalk')

            plt.legend([("#0000ff", "-", "#ff0000", "-"), ("#0000ff", (0, (3, 1, 1, 1)), "#ff0000", (0, (3, 1, 1, 1))),
                        ("#0080ff", "-", "#ff8000", "-"), ("#00dfff", "-", "#ffdf00", "-")],
                       ['Freq Response', 'Crosstalk', '2ⁿᵈ Harmonic', '3ʳᵈ Harmonic'],
                       handler_map={tuple: AnyObjectHandler()},loc=4)

            if len(aox0) > 0  and len(aox1) > 0:
                axs[0].set_ylim((min(chain(aox0, aox1)) -2), (max(chain(ao0, ao1)) +2))

        else:
            lines1, labels1 = axs[0].get_legend_handles_labels()
            lines2, labels2 = axtwin.get_legend_handles_labels()
            plt.legend(lines1 + lines2, labels1 + labels2, loc=4)
     
        new_lim1, new_lim2 = align_yaxis(axs[0], axtwin)
        axs[0].set_ylim(new_lim1)
        axtwin.set_ylim(new_lim2)

        axs[0].set_ylabel("Amplitude (dB)")
        axtwin.set_ylabel("Distortion (dB)")
        axs[0].set_xlabel("Frequency (Hz)")


    if PLOT_STYLE == 3:
        fig, axs = plt.subplots(2, 1, sharex=True, figsize=(14,6))

        axs[0].set_ylim(-5,5)

        if INPUT_FILE_1:
            if (min(chain(ao0, ao1)) <-5) or (max(chain(ao0, ao1)) >5):
                axs[0].autoscale(enable=True, axis='y')
        elif (min(ao0) <-5) or (max(ao0) >5):
                axs[0].autoscale(enable=True, axis='y')

        if OVERRIDE_Y_LIMIT == 1:
            axs[0].set_ylim(*OVERRIDE_Y_LIMIT_VALUE)

        axs[0].semilogx(fo0,ao0,color = '#0000ff', label = 'Freq Response')
        axs[1].semilogx(fo2h0,ao2h0,color = '#0080ff', label = '2nd Harmonic')
        axs[1].semilogx(fo3h0,ao3h0,color = '#00dfff', label = '3rd Harmonic')


        if file1_data:
            axs[0].semilogx(fo1,ao1, color = '#ff0000', label = 'Freq Response')

            axs[1].semilogx(fo2h1,ao2h1,color = '#ff8000', label = '2ⁿᵈ Harmonic')
            axs[1].semilogx(fo3h1,ao3h1,color = '#ffdf00', label = '3ʳᵈ Harmonic')

            axs[0].legend([("#0000ff", "-", "#ff0000", "-"),],
                       ['Freq Response'],
                       handler_map={tuple: AnyObjectHandler()},loc=4)
     
            axs[1].legend([("#0080ff", "-", "#ff8000", "-"), ("#00dfff", "-", "#ffdf00", "-")],
                       ['2ⁿᵈ Harmonic', '3ʳᵈ Harmonic'],
                       handler_map={tuple: AnyObjectHandler()},loc=4)

        else:
            axs[0].legend(loc=4)
            axs[1].legend(loc=4)

        axs[0].set_ylabel("Amplitude (dB)")
        axs[1].set_ylabel("Distortion (dB)")
        axs[1].set_xlabel("Frequency (Hz)")


    if PLOT_STYLE == 4:
        fig, axs = plt.subplots(2, 1, sharex=True, figsize=(14,10))
        axtwin = axs[1].twinx()

        axs[0].set_ylim(-5,5)

        if max(ao0) <7:
            axs[1].set_ylim(-25, 7)

        if max(ao0) < 4:
            axs[1].set_ylim(-25,5)
     
        if max(ao0) < 2:
            axs[1].set_ylim(-29,3)

        if max(ao0) < 0.5:
            axs[1].set_ylim(-30,2)

        if len(aox0) > 0:
            if INPUT_FILE_1:
                axs[1].set_ylim((min(chain(aox0, aox1)) -2), (max(chain(ao0, ao1)) +2))
            else:
                axs[1].set_ylim((min(aox0) -2), (max(ao0) +2))
 
        if OVERRIDE_Y_LIMIT == 1:
            axs[1].set_ylim(*OVERRIDE_Y_LIMIT_VALUE)

 
        axs[1].semilogx(fo0,ao0, color = '#0000ff', label = 'Freq Response')

        axtwin.semilogx(fo2h0,ao2h0,color = '#0080ff', label = '2ⁿᵈ Harmonic', alpha = 1, linewidth = 0.75)
        axtwin.semilogx(fo3h0,ao3h0,color = '#00dfff', label = '3ʳᵈ Harmonic', alpha = 1, linewidth = 0.75)

        axs[1].semilogx(fox0,aox0,color = '#0000ff', linestyle = (0, (3, 1, 1, 1)), label = 'Crosstalk')
 
 
        if file1_data:
            axs[1].semilogx(fo1,ao1, color = '#ff0000', label = 'Freq Response')

            axtwin.semilogx(fo2h1,ao2h1,color = '#ff8000', label = '2ⁿᵈ Harmonic', alpha = 1, linewidth = 0.75)
            axtwin.semilogx(fo3h1,ao3h1,color = '#ffdf00', label = '3ʳᵈ Harmonic', alpha = 1, linewidth = 0.75)

            axs[1].semilogx(fox1,aox1,color = '#ff0000', linestyle = (0, (3, 1, 1, 1)), label = 'Crosstalk')

            plt.legend([("#0000ff", "-", "#ff0000", "-"), ("#0000ff", (0, (3, 1, 1, 1)), "#ff0000", (0, (3, 1, 1, 1))),
                        ("#0080ff", "-", "#ff8000", "-"), ("#00dfff", "-", "#ffdf00", "-")],
                       ['Freq Response', 'Crosstalk', '2ⁿᵈ Harmonic', '3ʳᵈ Harmonic'],
                       handler_map={tuple: AnyObjectHandler()},loc=4)

            if len(aox0) > 0  and len(aox1) > 0:
                axs[1].set_ylim((min(chain(aox0, aox1)) -2), (max(chain(ao0, ao1)) +2))

        else:
            lines1, labels1 = axs[1].get_legend_handles_labels()
            lines2, labels2 = axtwin.get_legend_handles_labels()
            plt.legend(lines1 + lines2, labels1 + labels2, loc=4)
     
        new_lim1, new_lim2 = align_yaxis(axs[1], axtwin)
        axs[1].set_ylim(new_lim1)
        axtwin.set_ylim(new_lim2)

        if file1_data:
            if (min(chain(ao0, ao1)) <-5) or (max(chain(ao0, ao1)) >5):
                axs[0].autoscale(enable=True, axis='y')
        elif (min(ao0) <-5) or (max(ao0) >5):
                axs[0].autoscale(enable=True, axis='y')

        if OVERRIDE_Y_LIMIT == 1:
            axs[0].set_ylim(*OVERRIDE_Y_LIMIT_VALUE)

        axs[0].semilogx(fo0,ao0,color = '#0000ff', label = 'Freq Response')
     
        if file1_data:
            axs[0].semilogx(fo1,ao1, color = '#ff0000', label = 'Freq Response')
            axs[0].legend([("#0000ff", "-", "#ff0000", "-"),],
                       ['Freq Response'],
                       handler_map={tuple: AnyObjectHandler()},loc=4)

        else:
            axs[0].legend(loc=4)     

        axs[0].set_ylabel("Amplitude (dB)")
        axs[1].set_ylabel("Amplitude (dB)")
        axtwin.set_ylabel("Distortion (dB)")
        axs[1].set_xlabel("Frequency (Hz)")

        gs = GridSpec(2, 1, height_ratios=[1, 2])
        axs[0].set_position(gs[0].get_position(fig))
        axs[1].set_position(gs[1].get_position(fig))

    if PLOT_STYLE == 5:
        fig, axs = plt.subplots(1, 1, figsize=(14,3))
        axs = np.ravel([axs])

        axs[0].set_ylim(-5,5)

        if file1_data:
            if (min(chain(ao0, ao1)) <-5) or (max(chain(ao0, ao1)) >5):
                axs[0].autoscale(enable=True, axis='y')
        elif (min(ao0) <-5) or (max(ao0) >5):
                axs[0].autoscale(enable=True, axis='y')

        if OVERRIDE_Y_LIMIT == 1:
            axs[0].set_ylim(*OVERRIDE_Y_LIMIT_VALUE)

        axs[0].semilogx(fo0,ao0,color = '#0000ff', label = 'Freq Response')
        
        if file1_data:
            axs[0].semilogx(fo1,ao1, color = '#ff0000', label = 'Freq Response')
            axs[0].legend([("#0000ff", "-", "#ff0000", "-"),],
                       ['Freq Response'],
                       handler_map={tuple: AnyObjectHandler()},loc=4)

        else:
            axs[0].legend(loc=4)
    
        axs[0].set_ylabel("Amplitude (dB)")
        axs[0].set_xlabel("Frequency (Hz)")


    for i, ax in enumerate(axs.flat):
 
        if FILE0NORM == 0:
            if  not (PLOT_STYLE == 3 and i != 0):
                ax.axline((NORMALIZE, 0), (NORMALIZE, 1), color = 'm', lw = 1)
        elif FILE0NORM == 1:
            if not (PLOT_STYLE == 3 and i != 0):
                ax.plot(NORMALIZE, 0, marker = 'x', color = 'm')
        
        anchored_text = AnchoredText('SJ', 
                            frameon=False, borderpad=0, pad=0.03, 
                            loc=1, bbox_transform=plt.gca().transAxes,
                            prop={'color':'m','fontsize':25,'alpha':.4,
                            'style':'oblique'})
        ax.add_artist(anchored_text)
        
        ax.grid(True, which="major", axis="both", ls="-", color="black")
        ax.grid(True, which="minor", axis="both", ls="-", color="gainsboro")

        ax.set_xticks([0,20,50,100,500,1000,5000,10000,20000,50000,100000])
        #ax.set_xticklabels(['0','20','50','100','500','1k','5k','10k','20k','50k','100k'])


    bbox_args = dict(boxstyle="round", color='b', fc='w', ec='b', alpha=1, pad=.15)
    axs[0].annotate('+' + str(deltah0) + ', ' + u"\u2212" + str(deltal0) + ' dB',color = 'b',\
             xy=(fo0[0],(ao0[0]-1)), xycoords='data', \
             xytext=(-10, -20), textcoords='offset points', \
             ha="left", va="center", bbox=bbox_args)

    if file1_data:
        bbox_args = dict(boxstyle="round", color='b', fc='w', ec='r', alpha=1, pad=.15)
        axs[0].annotate('+' + str(deltah1) + ', ' + u"\u2212" + str(deltal1) + ' dB',color = 'r',\
                 xy=(fo0[0],(ao0[0]-1)), xycoords='data', \
                 xytext=(-10, -34.5), textcoords='offset points', \
                 ha="left", va="center", bbox=bbox_args)

    #plt.autoscale(enable=True, axis='x')

    for ax in axs.flat:
        # Get x-range from first line only (main frequency response)
        lines = ax.get_lines()
        if lines:
            x_data = lines[0].get_xdata()
            if len(x_data) > 0:
                xmin = np.min(x_data)
                xmax = np.max(x_data)
                if xmin > 0:  # Valid for log scale
                    log_xmin = np.log10(xmin)
                    log_xmax = np.log10(xmax)
                    log_range = log_xmax - log_xmin
                    margin_frac = 0.05  # 5% of range, as before
                    min_margin_decades = 0.02  # e.g., 0.1 decade (~26% margin for 1000-2000 Hz)
                    margin = max(margin_frac * log_range, min_margin_decades)
                    new_log_xmin = log_xmin - margin
                    new_log_xmax = log_xmax + margin
                    ax.set_xlim(10**new_log_xmin, 10**new_log_xmax)
                    actual_xlim = ax.get_xlim()
                    logger.debug(f"Actual xlim: ({actual_xlim[0]:.0f}, {actual_xlim[1]:.0f})")

        ax.xaxis.set_major_formatter(FuncFormatter(format_freq))
        
        # Check the axis range in decades (log scale)
        xlim = ax.get_xlim()
        if xlim[0] > 0:  # Avoid log(0)
            decades = np.log10(xlim[1] / xlim[0])
            
            # Get LogFormatter's minor_thresholds setting
            minor_fmt = ax.xaxis.get_minor_formatter()
            if hasattr(minor_fmt, 'minor_thresholds'):
                threshold = minor_fmt.minor_thresholds[0]  # Default is 2
                
                # If range is less than threshold decades, LogFormatter labels minors
                if decades < threshold:
                    ax.xaxis.set_minor_formatter(FuncFormatter(format_freq))


    axs[0].set_title(PLOT_INFO + "\n", fontsize=16)

    now = datetime.now()

    # Position text below bottom axes using blended transform
    # This maintains horizontal position while placing vertically relative to axes
    bottom_ax = axs[-1] if isinstance(axs, np.ndarray) else axs
    
    # Calculate vertical position from axes bottom
    ax_height_inches = bottom_ax.get_position().height * fig.get_figheight()
    y_in_axes_coords = -0.6 / ax_height_inches
    
    # Use blended transform: figure x-coords (for layout) + axes y-coords (for bbox_inches='tight')
    from matplotlib.transforms import blended_transform_factory
    trans = blended_transform_factory(fig.transFigure, bottom_ax.transAxes)
    
    fig.text(0.125, y_in_axes_coords, EQUIP_INFO, alpha=.75, fontsize=10,
             ha='left', va='top', transform=trans)
    fig.text(0.9, y_in_axes_coords, AUTHOR, alpha=.75, fontsize=10,
             ha='right', va='top', transform=trans)


    if environment == 'web':
        import io
        import base64

        plt.figtext(.17, .118, "sjplot.com/online" + "\n" + "SJPlot " + __version__  + "\n" + \
            now.strftime("%b %d, %Y %H:%M"), fontsize=6)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=192, bbox_inches='tight', pad_inches=.5)
        buf.seek(0)
        img_data = base64.b64encode(buf.read()).decode()
        buf.close()

        # Call the JavaScript function to update the UI
        from js import window
        window.updateUIWithPlotImage(img_data)

        return img_data

    else:

        if file1_data:
            plt.figtext(.17, .118, "SJPlot " + __version__ + "\n" + INPUT_FILE_0 + "\n" + INPUT_FILE_1 + "\n" + \
                now.strftime("%b %d, %Y %H:%M"), fontsize=6)
        else:
            plt.figtext(.17, .118, "SJPlot " + __version__ + "\n" + INPUT_FILE_0 + "\n" + \
                now.strftime("%b %d, %Y %H:%M"), fontsize=6)

        plt.savefig(PLOT_INFO.replace(' / ', '_') + '.png', bbox_inches='tight', pad_inches=.5, dpi=192)
        plt.show()

    logger.info(f"Done!")


if __name__ == "__main__":
    main()
