'''
PLEASE READ

DO NOT EDIT THIS SCRIPT!

Configuration is now stored in a separate file with the default name "SJPlot.cfg"  This file should be in
the same directory that this script is run from.

You can also pass the configuration via the command line: "python sjplot.py --help" for syntax.

Details in the README here: https://github.com/FidelisAnalog/SJPlot/tree/Splitter
'''


from scipy.signal import find_peaks, sosfiltfilt, iirfilter, lfilter, resample
from scipy.ndimage import uniform_filter1d
from scipy.io.wavfile import read, write
from pathlib import Path
from matplotlib.legend_handler import HandlerBase
from matplotlib.offsetbox import AnchoredText
from itertools import chain
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import numpy as np
import os
import logging
import argparse
import configparser
import io
import base64
from js import document, console
import time


__version__ = "18.4.0"


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
    parser.add_argument("--plot_style", type=int, choices=[1, 2, 3, 4, 5], help="The plot style to output.")
    parser.add_argument("--plot_data_out", default=None, action="store_true", help="Output plot data.")
    parser.add_argument("--round_level", type=int, help="{integer} Rounding level.", metavar ="")
    parser.add_argument("--riaa_mode", type=int, choices=[0, 1, 2, 3], help="0 = none, 1 = bass, 2 = treble, 3 = both.")
    parser.add_argument("--riaa_inverse", default=None, action="store_true", help="Invert RIAA filter(s).")
    parser.add_argument("--str100", default=None, action="store_true", help="Apply STR100 correction.")
    parser.add_argument("--xg7001", default=None, action="store_true", help="Apply XG7001 correction.")
    parser.add_argument("--normalize", type=int, help="{integer} Frequency in Hz to normalize at.", metavar = "")
    parser.add_argument("--file0norm", default=None, action="store_true", help="Normalize both files to file_0.")
    parser.add_argument("--onekfstart", default=None, action="store_true", help="Start the plot at 1kHz.")
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
        "plot_style": 4,
        "plot_data_out": False,
        "round_level": 1,
        "riaa_mode": 2,
        "riaa_inverse": True,
        "str100": False,
        "xg7001": False,
        "normalize": 1000,
        "file0norm": False,
        "onekfstart": False,
        "end_f": 20000,
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
            for key, value in web_config.items():
                if key in combined_config:
                    combined_config[key] = value
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
 

def ft_window(n):       #Matlab's flat top window
    w = []
    a0 = 0.21557895
    a1 = 0.41663158
    a2 = 0.277263158
    a3 = 0.083578947
    a4 = 0.006947368
    pi = np.pi

    for x in range(0,n):
        w.append(a0 - a1*np.cos(2*pi*x/(n-1)) + a2*np.cos(4*pi*x/(n-1)) - a3*np.cos(6*pi*x/(n-1)) + a4*np.cos(8*pi*x/(n-1)))
    return w


def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx


def createplotdata(signal, Fs, iteration=None, norm=None, onekfstart=0, end_f=20000, str100=0, file0norm=0, normalize=1000):
    if iteration is None:
        iteration = [0]
    if norm is None:
        norm = [0]

    def interpolate(f, a, minf, maxf, fstep):
        # Ensure inputs are NumPy arrays
        f = np.array(f)
        a = np.array(a)

        bins = np.arange(minf, maxf + fstep, fstep)  # Define bin edges
        indices = np.digitize(f, bins) - 1  # Find the bin index for each frequency
        f_out, a_out = [], []

        for i, bin_center in enumerate(bins):
            mask = (indices == i)  # Select frequencies that fall into the current bin
            if np.any(mask):  # Check if any values are in the bin
                avg_amp = np.mean(a[mask])  # Compute the average amplitude
                f_out.append(bin_center)
                a_out.append(20 * np.log10(avg_amp))
        
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


    def chunk(signal, Fs, fmin, fmax, step, offset):
        # Perform FFT analysis
        f, a, fx, ax, f2, a2, f3, a3 = rfft(signal, Fs, fmin, fmax, step)

        # Interpolate frequencies and amplitudes
        f, a = interpolate(f, a, fmin, fmax, step)
        fx, ax = interpolate(fx, ax, fmin, fmax, step)
        f2, a2 = interpolate(f2, a2, fmin, fmax, step)
        f3, a3 = interpolate(f3, a3, fmin, fmax, step)

        # Normalize amplitudes in a single line
        a, ax, a2, a3 = [
            [amp_val - offset for amp_val in amp_list]
            for amp_list in (a, ax, a2, a3)
        ]

        return f, a, fx, ax, f2, a2, f3, a3
 

    def concat(f, a, fx, ax, f2, a2, f3, a3, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3):
        # Use list.extend for efficiency and clarity
        fout.extend(f)
        aout.extend(a)
        foutx.extend(fx)
        aoutx.extend(ax)
        fout2.extend(f2)
        aout2.extend(a2)
        fout3.extend(f3)
        aout3.extend(a3)

        return fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3

    # Helper function to handle chunking and concatenation
    def process_chunk(signal, Fs, fmin, fmax, step, offset, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3):
        f, a, fx, ax, f2, a2, f3, a3 = chunk(signal, Fs, fmin, fmax, step, offset)
        return concat(f, a, fx, ax, f2, a2, f3, a3, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)


    # Initialize output variables
    fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = [], [], [], [], [], [], [], []

    # Process frequency chunks
    if onekfstart == 0:
        fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = process_chunk(signal, Fs, 20, 45, 5, 26.03, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)
        fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = process_chunk(signal, Fs, 50, 90, 10, 19.995, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)
        fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = process_chunk(signal, Fs, 100, 980, 20, 13.99, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)

    fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = process_chunk(signal, Fs, 1000, end_f, 100, 0, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)



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
    aout, aoutx, aout2, aout3 = [amp - norm[0] for amp in (aout, aoutx, aout2, aout3)]
 
    # Apply low-pass filter
    sos = iirfilter(3, 0.5, btype='lowpass', output='sos')  # Low-pass filter
    aout = sosfiltfilt(sos, aout)
    aout2 = sosfiltfilt(sos, aout2)
    aout3 = sosfiltfilt(sos, aout3)
    if aoutx.size > 0:
        aoutx = sosfiltfilt(sos, aoutx)

    iteration[0]+=1

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

    '''
    logger.info(f"Reading: {input_file}")
    
    if environment == 'web':
        # Handle byte stream
        logger.info(f"Reading: Byte stream input ({input_file.getbuffer().nbytes} bytes)")
        with io.BytesIO(input_data) as wav_io:
            Fs, audio = read(wav_io)
    else:
        # Handle file path
        logger.info(f"Reading: {input_file}")
        Fs, audio = read(input_data)
    '''

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

            output_file_left = os.path.splitext(input_file)[0] + '_L.wav'
            output_file_right = os.path.splitext(input_file)[0] + '_R.wav'

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
            print('norm 0')
        except NameError:
            audio_2 = None
            print('norm 1')
    elif extract_sweeps != 1:
        audio_2 = None


    audio, minf, maxf = ordersignal(audio, Fs)
    
    logger.info(f"Raw sweep from {minf * 100:.0f}Hz to {maxf * 100:.0f}Hz")
    #logger.info(f"Raw sweep maximum frequency: {maxf * 100:.0f}Hz")
 
    return audio, audio_2, Fs


def slice_audio(signal, Fs, test_record):
    # Rotation Helper
    def rotate_left(y_in, nd):
        return np.concatenate((y_in[nd:], y_in[:nd]))


    # Filter
    def apply_filter(signal, low, high, Fs, order=17, btype='band'):
        if btype == 'band':
            sos = iirfilter(order, [low, high], rs=140, btype='band', analog=False, ftype='cheby2', fs=Fs, output='sos')
            
        elif btype == 'high':
            sos = iirfilter(order, high, rs=140, btype='highpass', analog=False, ftype='cheby2', fs=Fs, output='sos')

        return sosfiltfilt(sos, signal)


    def find_burst_bounds(signal, Fs, lower_border, upper_border, consecutive_in_borders=10, threshold=0.02, shift_size=12, shiftings=3):
        # Detect peaks with constraints on minimum distance
        peaks, _ = find_peaks(signal, height=threshold, distance=lower_border)#prominence=.5)
        logger.debug(f"Peaks Found: {len(peaks)}")

        # Find valid sequences of peak spacing
        valid_diffs = (lower_border <= np.diff(peaks)) & (np.diff(peaks) <= upper_border)
        start_index = np.argmax(np.convolve(valid_diffs, np.ones(consecutive_in_borders, dtype=int), mode='valid') == consecutive_in_borders)

        start_sample = peaks[start_index]
        logger.debug(f"Start Index: {start_sample}")
        
        # Define burst region
        is_ = int(start_sample + (1 * Fs))  # Start 1s after the first peak
        ie = int(start_sample + (14 * Fs))  # End 14s after

        # Extract and smooth burst region
        cut_burst = signal[is_:ie]
        cut_burst = uniform_filter1d(cut_burst, size=shift_size * shiftings)

        # Normalize and find burst end
        cut_burst /= np.max(cut_burst)
        burst_end = np.argmax(cut_burst < threshold)

        end_sample = is_ + burst_end

        logger.debug(f"End Index: {end_sample}")
        
        return start_sample, end_sample


    def find_end_of_sweep(sweep_start_sample, sweep_end_min, sweep_end_max, signal, Fs, threshold=0.05, shiftings=6):
        sample_offset_start = sweep_start_sample + int(Fs * sweep_end_min)
        sample_offset_end = sweep_start_sample + int(Fs * sweep_end_max)
        signal = signal[sample_offset_start:sample_offset_end]
        original_signal = signal

        logger.debug(f"Length of End Window: {len(signal)}")

        # Filter a bit by shifting and adding
        signal_shifted = rotate_left(signal, 1)
        for i in range(shiftings):
            signal = signal + signal_shifted
            signal_shifted = rotate_left(signal_shifted, 1)

        # Find end    
        signal = np.array(signal < threshold, dtype=float)
        signal = np.diff(signal)
        end_sample = np.argmax(signal) + sample_offset_start

        logger.debug(f"End Sample (Global Index): {end_sample}")
        logger.debug(f"Sample Offset Start: {sample_offset_start}, End: {sample_offset_end}")
        logger.debug(f"End Sample (Relative Index): {end_sample - sample_offset_start}")
        
        return end_sample


    # Test record parameters
    record_params = {
        'TRS1007': {'sweep_offset': 74, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
        'TRS1005': {'sweep_offset': 32, 'sweep_end_min': 26, 'sweep_end_max': 34, 'sweep_start_detect': 1},
        'STR100': {'sweep_offset': 74, 'sweep_end_min': 63, 'sweep_end_max': 67, 'sweep_start_detect': 0},
        'STR120': {'sweep_offset': 58, 'sweep_end_min': 45, 'sweep_end_max': 50, 'sweep_start_detect': 0},
        'STR130': {'sweep_offset': 82, 'sweep_end_min': 63, 'sweep_end_max': 67, 'sweep_start_detect': 0},
        'STR170': {'sweep_offset': 75, 'sweep_end_min': 63, 'sweep_end_max': 67, 'sweep_start_detect': 0},
        'QR2009': {'sweep_offset': 80, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
        'QR2010': {'sweep_offset': 24, 'sweep_end_min': 15, 'sweep_end_max': 18, 'sweep_start_detect': 0},
        'XG7001': {'sweep_offset': 78, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
        'XG7002': {'sweep_offset': 74, 'sweep_end_min': 26, 'sweep_end_max': 30, 'sweep_start_detect': 1},
        'XG7005': {'sweep_offset': 78, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
	    'DIN45543': {'sweep_offset': 78, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
	    'ИЗМ33С0327': {'sweep_offset': 58, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
    }

    if test_record.upper() not in record_params:
        raise ValueError("Invalid test record.")

    params = record_params[test_record.upper()]

    left = signal[:, 0]
    right = signal[:, 1]

    logger.info(f"Test Record: {test_record}")

    lower_border = int(Fs/2040) # 1020Hz - have to scale with Fs
    upper_border = int(Fs/1960) # 980Hz

    # Filter and maximize for end of left pilot detection
    left_filtered = apply_filter(left, 500, 2000, Fs, btype='band')
    left_normalized = np.abs(left_filtered) / np.max(np.abs(left_filtered))

    # Find end of left pilot tone / start of sweep
    _, start_left_sweep = find_burst_bounds(left_normalized, Fs, lower_border, upper_border)

    if params['sweep_start_detect'] == 1:
        sample_offset = start_left_sweep + Fs
        start_left_sweep, _ = sample_offset + find_burst_bounds(left_normalized[sample_offset:], Fs, lower_border, upper_border)

    logger.info(f"Start of Left Sweep: {start_left_sweep}")

    # Filter and maximize for end of right pilot detection
    right_filtered = apply_filter(right, 500, 2000, Fs, btype='band')
    right_normalized = np.abs(right_filtered) / np.max(np.abs(right_filtered))

    # Find end of left pilot tone / start of sweep
    sample_offset = start_left_sweep + int(Fs * params['sweep_offset'])
    _, start_right_sweep = sample_offset + find_burst_bounds(right_normalized[sample_offset:], Fs, lower_border, upper_border)

    if params['sweep_start_detect'] == 1:
        sample_offset = start_right_sweep + Fs
        start_right_sweep, _ = sample_offset + find_burst_bounds(right_normalized[sample_offset:], Fs, lower_border, upper_border)

    logger.info(f"Start of Right Sweep: {start_right_sweep}")

    # Filter and maximize for end of left sweep detection
    left_filtered = apply_filter(left, None, 10000, Fs, btype='high')
    left_normalized = np.abs(left_filtered) / np.max(np.abs(left_filtered))

    # Find end of left sweep
    end_left_sweep = find_end_of_sweep(start_left_sweep, params['sweep_end_min'], params['sweep_end_max'], left_normalized, Fs)
    logger.info(f"End of Left Sweep: {end_left_sweep}")

    # Filter and maximize for end of right sweep detection
    right_filtered = apply_filter(right, None, 10000, Fs, btype='high')
    right_normalized = np.abs(right_filtered) / np.max(np.abs(right_filtered))

    # Find end of right sweep
    end_right_sweep = find_end_of_sweep(start_right_sweep, params['sweep_end_min'], params['sweep_end_max'], right_normalized, Fs)
    logger.info(f"End of Right Sweep: {end_right_sweep}")

    logger.info(f"Left Sweep Duration: {(end_left_sweep-start_left_sweep)/Fs:.4f}")
    logger.info(f"Right Sweep Duration: {(end_right_sweep-start_right_sweep)/Fs:.4f}")

    left_slice = np.column_stack((left[start_left_sweep:end_left_sweep], right[start_left_sweep:end_left_sweep]))
    right_slice = np.column_stack((right[start_right_sweep:end_right_sweep], left[start_right_sweep:end_right_sweep]))

    logger.info(f"Sweep extraction completed.")

    return left_slice, right_slice


def main():
    """
    Main entry point for SJPlot analysis.
    Can be called from standalone mode or web environment.
    """
    config = get_config()

    INPUT_FILE_0 = config["file_0"]
    INPUT_FILE_1 = config["file_1"]
    EXTRACT_SWEEPS = config["extract_sweeps"]
    SAVE_SWEEPS = config["save_sweeps"]
    TEST_RECORD = config["test_record"]
    PLOT_INFO = config["plot_info"]
    EQUIP_INFO = config["equip_info"]
    PLOT_STYLE = config["plot_style"]
    PLOT_DATA_OUT = config["plot_data_out"]
    ROUND_LEVEL = config["round_level"]
    RIAA_MODE = config["riaa_mode"]
    RIAA_INVERSE = config["riaa_inverse"]
    STR100 = config["str100"]
    XG7001 = config["xg7001"]
    NORMALIZE = config["normalize"]
    FILE0NORM = config["file0norm"]
    ONEKFSTART = config["onekfstart"]
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

    '''
    if environment == 'web':
        from js import window
        file0_bytes = bytes(window.js_file0_data.to_py())
        file1_bytes = bytes(window.js_file1_data.to_py()) if window.js_file1_data else None

        audio0, Fs0 = get_audio(file0_bytes, environment)
        if file1_bytes:
            audio1, Fs1 = get_audio(file1_bytes, environment)
    else:
        audio0, Fs0 = get_audio("path_to_file0.wav", environment)
        audio1, Fs1 = get_audio("path_to_file1.wav", environment)
    '''


    if EXTRACT_SWEEPS == 1:
        input_sig_0, input_sig_1, Fs = get_audio(file0_data, environment, EXTRACT_SWEEPS, TEST_RECORD, SAVE_SWEEPS, RIAA_MODE, RIAA_INVERSE, XG7001)

        fo0, ao0, fox0, aox0, fo2h0, ao2h0, fo3h0, ao3h0 = createplotdata(input_sig_0, Fs, onekfstart=ONEKFSTART, end_f=END_F, str100=STR100, file0norm=FILE0NORM, normalize=NORMALIZE)

        deltaadj = ao0[find_nearest(fo0, NORMALIZE)]
        deltah0 = round((max(ao0 - deltaadj)), ROUND_LEVEL)
        deltal0 = abs(round((min(ao0 - deltaadj)), ROUND_LEVEL))

        logger.info(f"Left crosstalk @1kHz: {aox0[find_nearest(fox0, 1000)]:.2f}dB")

        fo1, ao1, fox1, aox1, fo2h1, ao2h1, fo3h1, ao3h1 = createplotdata(input_sig_1, Fs, onekfstart=ONEKFSTART, end_f=END_F, str100=STR100, file0norm=FILE0NORM, normalize=NORMALIZE)
 
        deltaadj = ao1[find_nearest(fo1, NORMALIZE)]
        deltah1 = round((max(ao1 - deltaadj)), ROUND_LEVEL)
        deltal1 = abs(round((min(ao1 - deltaadj)), ROUND_LEVEL))

        logger.info(f"Right crosstalk @1kHz: {aox1[find_nearest(fox1, 1000)]:.2f}dB")

        INPUT_FILE_1 = '_'


    else:
        input_sig, _, Fs = get_audio(file0_data, environment, riaa_mode=RIAA_MODE, riaa_inverse=RIAA_INVERSE, xg7001=XG7001)
        fo0, ao0, fox0, aox0, fo2h0, ao2h0, fo3h0, ao3h0 = createplotdata(input_sig, Fs, onekfstart=ONEKFSTART, end_f=END_F, str100=STR100, file0norm=FILE0NORM, normalize=NORMALIZE)

        deltaadj = ao0[find_nearest(fo0, NORMALIZE)]
        deltah0 = round((max(ao0 - deltaadj)), ROUND_LEVEL)
        deltal0 = abs(round((min(ao0 - deltaadj)), ROUND_LEVEL))

        if aox0.size > 0:
            logger.info(f"Left crosstalk @1kHz: {aox0[find_nearest(fox0, 1000)]:.2f}dB")


        if file1_data:
            input_sig, _, Fs = get_audio(file1_data, environment, riaa_mode=RIAA_MODE, riaa_inverse=RIAA_INVERSE, xg7001=XG7001)
            fo1, ao1, fox1, aox1, fo2h1, ao2h1, fo3h1, ao3h1 = createplotdata(input_sig, Fs, onekfstart=ONEKFSTART, end_f=END_F, str100=STR100, file0norm=FILE0NORM, normalize=NORMALIZE)
     
            deltaadj = ao1[find_nearest(fo1, NORMALIZE)]
            deltah1 = round((max(ao1 - deltaadj)), ROUND_LEVEL)
            deltal1 = abs(round((min(ao1 - deltaadj)), ROUND_LEVEL))

            if aox1.size > 0:
                logger.info(f"Right crosstalk @1kHz: {aox1[find_nearest(fox1, 1000)]:.2f}dB")


    if PLOT_DATA_OUT == 1:

        dao0 = [*ao0, *[''] * (len(fo0) - len(ao0))]
        daox0 = [*aox0, *[''] * (len(fo0) - len(aox0))]
        dao2h0 = [*ao2h0, *[''] * (len(fo0) - len(ao2h0))]
        dao3h0 = [*ao3h0, *[''] * (len(fo0) - len(ao3h0))]

        print('\n\nFile 0 Plot Data: (freq, ampl, x-talk, 2h, 3h)\n\n')

        dataout = list(zip(fo0, dao0, daox0, dao2h0, dao3h0))
        for fo, ao, aox, ao2, ao3 in dataout:
            print(fo, ao, aox, ao2, ao3, sep=', ')

        if INPUT_FILE_1:
            dao1 = [*ao1, *[''] * (len(fo1) - len(ao1))]
            daox1 = [*aox1, *[''] * (len(fo1) - len(aox1))]
            dao2h1 = [*ao2h1, *[''] * (len(fo1) - len(ao2h1))]
            dao3h1 = [*ao3h1, *[''] * (len(fo1) - len(ao3h1))]

            print('\n\nFile 1 Plot Data: (freq, ampl, x-talk, 2h, 3h)\n\n')

            dataout = list(zip(fo1, dao1, daox1, dao2h1, dao3h1))
            for fo, ao, aox, ao2, ao3 in dataout:
                print(fo, ao, aox, ao2, ao3, sep=', ')


    plt.rcParams["xtick.minor.visible"] =  True
    plt.rcParams["ytick.minor.visible"] =  True

    if PLOT_STYLE == 1:
        fig, axs = plt.subplots(1, 1, figsize=(14,6))
        axs = np.ravel([axs])

        axs[0].semilogx(fo0,ao0, color = '#0000ff', label = 'Freq Response')

        axs[0].semilogx(fo2h0,ao2h0,color = '#0080ff', label = '2ⁿᵈ Harmonic', alpha = 1, linewidth = 0.75)
        axs[0].semilogx(fo3h0,ao3h0,color = '#00dfff', label = '3ʳᵈ Harmonic', alpha = 1, linewidth = 0.75)

        axs[0].semilogx(fox0,aox0,color = '#0000ff', linestyle = (0, (3, 1, 1, 1)), label = 'Crosstalk')
 

        if INPUT_FILE_1:
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


        if aox0.size > 0:
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
 
 
        if INPUT_FILE_1:
            axs[0].semilogx(fo1,ao1, color = '#ff0000', label = 'Freq Response')

            axtwin.semilogx(fo2h1,ao2h1,color = '#ff8000', label = '2ⁿᵈ Harmonic', alpha = 1, linewidth = 0.75)
            axtwin.semilogx(fo3h1,ao3h1,color = '#ffdf00', label = '3ʳᵈ Harmonic', alpha = 1, linewidth = 0.75)

            axs[0].semilogx(fox1,aox1,color = '#ff0000', linestyle = (0, (3, 1, 1, 1)), label = 'Crosstalk')

            plt.legend([("#0000ff", "-", "#ff0000", "-"), ("#0000ff", (0, (3, 1, 1, 1)), "#ff0000", (0, (3, 1, 1, 1))),
                        ("#0080ff", "-", "#ff8000", "-"), ("#00dfff", "-", "#ffdf00", "-")],
                       ['Freq Response', 'Crosstalk', '2ⁿᵈ Harmonic', '3ʳᵈ Harmonic'],
                       handler_map={tuple: AnyObjectHandler()},loc=4)

            if aox0.size > 0  and aox1.size > 0:
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


        if INPUT_FILE_1:
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

        if aox0.size > 0:
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
 
 
        if INPUT_FILE_1:
            axs[1].semilogx(fo1,ao1, color = '#ff0000', label = 'Freq Response')

            axtwin.semilogx(fo2h1,ao2h1,color = '#ff8000', label = '2ⁿᵈ Harmonic', alpha = 1, linewidth = 0.75)
            axtwin.semilogx(fo3h1,ao3h1,color = '#ffdf00', label = '3ʳᵈ Harmonic', alpha = 1, linewidth = 0.75)

            axs[1].semilogx(fox1,aox1,color = '#ff0000', linestyle = (0, (3, 1, 1, 1)), label = 'Crosstalk')

            plt.legend([("#0000ff", "-", "#ff0000", "-"), ("#0000ff", (0, (3, 1, 1, 1)), "#ff0000", (0, (3, 1, 1, 1))),
                        ("#0080ff", "-", "#ff8000", "-"), ("#00dfff", "-", "#ffdf00", "-")],
                       ['Freq Response', 'Crosstalk', '2ⁿᵈ Harmonic', '3ʳᵈ Harmonic'],
                       handler_map={tuple: AnyObjectHandler()},loc=4)

            if aox0.size > 0  and aox1.size > 0:
                axs[1].set_ylim((min(chain(aox0, aox1)) -2), (max(chain(ao0, ao1)) +2))

        else:
            lines1, labels1 = axs[1].get_legend_handles_labels()
            lines2, labels2 = axtwin.get_legend_handles_labels()
            plt.legend(lines1 + lines2, labels1 + labels2, loc=4)
     
        new_lim1, new_lim2 = align_yaxis(axs[1], axtwin)
        axs[1].set_ylim(new_lim1)
        axtwin.set_ylim(new_lim2)

        if INPUT_FILE_1:
            if (min(chain(ao0, ao1)) <-5) or (max(chain(ao0, ao1)) >5):
                axs[0].autoscale(enable=True, axis='y')
        elif (min(ao0) <-5) or (max(ao0) >5):
                axs[0].autoscale(enable=True, axis='y')

        if OVERRIDE_Y_LIMIT == 1:
            axs[0].set_ylim(*OVERRIDE_Y_LIMIT_VALUE)

        axs[0].semilogx(fo0,ao0,color = '#0000ff', label = 'Freq Response')
     
        if INPUT_FILE_1:
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

        if INPUT_FILE_1:
            if (min(chain(ao0, ao1)) <-5) or (max(chain(ao0, ao1)) >5):
                axs[0].autoscale(enable=True, axis='y')
        elif (min(ao0) <-5) or (max(ao0) >5):
                axs[0].autoscale(enable=True, axis='y')

        if OVERRIDE_Y_LIMIT == 1:
            axs[0].set_ylim(*OVERRIDE_Y_LIMIT_VALUE)

        axs[0].semilogx(fo0,ao0,color = '#0000ff', label = 'Freq Response')

        if INPUT_FILE_1:
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
        ax.set_xticklabels(['0','20','50','100','500','1k','5k','10k','20k','50k','100k'])


    bbox_args = dict(boxstyle="round", color='b', fc='w', ec='b', alpha=1, pad=.15)
    axs[0].annotate('+' + str(deltah0) + ', ' + u"\u2212" + str(deltal0) + ' dB',color = 'b',\
             xy=(fo0[0],(ao0[0]-1)), xycoords='data', \
             xytext=(-10, -20), textcoords='offset points', \
             ha="left", va="center", bbox=bbox_args)

    if INPUT_FILE_1:
        bbox_args = dict(boxstyle="round", color='b', fc='w', ec='r', alpha=1, pad=.15)
        axs[0].annotate('+' + str(deltah1) + ', ' + u"\u2212" + str(deltal1) + ' dB',color = 'r',\
                 xy=(fo0[0],(ao0[0]-1)), xycoords='data', \
                 xytext=(-10, -34.5), textcoords='offset points', \
                 ha="left", va="center", bbox=bbox_args)

    plt.autoscale(enable=True, axis='x')

    axs[0].set_title(PLOT_INFO + "\n", fontsize=16)


    now = datetime.now()

    '''
    if INPUT_FILE_1:
        plt.figtext(.17, .118, "SJPlot v" + __version__ + "\n" + INPUT_FILE_0 + "\n" + INPUT_FILE_1 + "\n" + \
            now.strftime("%b %d, %Y %H:%M"), fontsize=6)
    else:
        plt.figtext(.17, .118, "SJPlot v" + __version__ + "\n" + INPUT_FILE_0 + "\n" + \
            now.strftime("%b %d, %Y %H:%M"), fontsize=6)
    '''

    plt.figtext(.125, 0, EQUIP_INFO, alpha=.75, fontsize=8)

    if environment == 'web':
        from js import window
        import io
        import base64

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=192, pad_inches=.5)
        buf.seek(0)
        img_data = base64.b64encode(buf.read()).decode()
        buf.close()

        # Update the web interface with results
        window.document.getElementById('output').innerHTML = f'<img src="data:image/png;base64,{img_data}" />'
        
        # Clear loading spinner and update status
        window.document.getElementById('loading').classList.remove('active')
        status_elem = window.document.getElementById('status')
        status_elem.textContent = '✅ Analysis Complete!'
        status_elem.className = 'success'
        
        # Re-enable analyze button
        window.document.getElementById('analyzeBtn').disabled = False

    else:
        plt.savefig(PLOT_INFO.replace(' / ', '_') +'.png', bbox_inches='tight', pad_inches=.5, dpi=192)
        plt.show()

    logger.info(f"Done!")

'''
def process_audio_web():
    try:
        # Retrieve file data from JavaScript variables
        from js import window, console
        import io
        import base64
        import numpy as np
        from scipy.io.wavfile import read
        import matplotlib.pyplot as plt

        start_time = time.time()

        # Convert JsProxy to bytes
        file0_bytes = bytes(window.js_file0_data.to_py())
        file1_bytes = bytes(window.js_file1_data.to_py()) if window.js_file1_data is not None else None

        # Debugging: Log the received data
        console.log("Processing file0_bytes:", len(file0_bytes))
        if file1_bytes is not None:
            console.log("Processing file1_bytes:", len(file1_bytes))

        # Convert file0_bytes to audio data
        with io.BytesIO(file0_bytes) as wav_io:
            Fs, audio0 = read(wav_io)

        # Convert file1_bytes to audio data if it exists
        if file1_bytes is not None:
            with io.BytesIO(file1_bytes) as wav_io:
                Fs1, audio1 = read(wav_io)
        else:
            audio1 = None  # Handle the absence of the second file

        # Ensure audio data is in NumPy array format
        audio0 = np.array(audio0)
        if audio1 is not None:
            audio1 = np.array(audio1)

        # Debugging: Log the audio data shapes
        console.log("Audio0 shape:", audio0.shape)
        if audio1 is not None:
            console.log("Audio1 shape:", audio1.shape)

        # Measure time for audio processing
        processing_start = time.time()

        # Process audio and generate plots
        # ...existing processing logic...

        processing_end = time.time()
        console.log("Audio processing time:", processing_end - processing_start)

        # Convert plot to base64 for web output
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_data = base64.b64encode(buf.read()).decode()

        # Update the web interface with results
        window.document.getElementById('output').innerHTML = f'<img src="data:image/png;base64,{img_data}" />'

        end_time = time.time()
        console.log("Total processing time:", end_time - start_time)

    except Exception as e:
        console.error(f"Error processing audio: {e}")

def handle_file_input(file_data, environment):
    """
    Handle file input based on the environment.
    - In standalone mode, file_data is a file path.
    - In web mode, file_data is a byte stream.
    """
    import io
    from scipy.io.wavfile import read

    if environment == 'web':
        with io.BytesIO(file_data) as wav_io:
            Fs, audio = read(wav_io)
    else:  # Standalone mode
        Fs, audio = read(file_data)

    return Fs, audio

def convert_plot_to_base64(fig):
    """
    Convert a matplotlib figure to a base64-encoded string.
    """
    import io
    import base64

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=192, bbox_inches='tight')
    buf.seek(0)
    img_data = base64.b64encode(buf.read()).decode()
    buf.close()

    return img_data
'''


if __name__ == "__main__":
    main()
