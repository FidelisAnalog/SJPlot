'''
PLEASE READ
To use this script you need to edit the user parameters section. The .wav file can be any
monotonic frequency sweep either up or down in frequency but it must be trimmed at both
ends to remove any leading silence.

The info_line should be alpha-numeric with entries separated by " / " only.  The script
will save a .png file that is named from the info line, replacing " / " with "_".  As
example "this / is / a / test" will create a file named "this_is_a_test.png".

INPUT_FILE_0 =      The first (L) file to plot, or the only file to plot, or the file you want
                    to extract sweeps from. 

INPUT_FILE_1 =      The second (R) file to plot.  If using one file change to = ''.  If you're
                    extracting sweeps, this parameter is ignored.

SPLIT_INPUT_FILE =  0 - Do not process the file for extraction of sweeps
                    1 - Extract the sweeps from INPUT_FILE_0.

SAVE_SPLIT_FILES =  0 - Do not save files
                    1 - The extract sweeps will be saved, appending either an "_L" or "_R" to the
                        INPUT_FILE_0 filename for the left and right sweeps, respectively.

TEST_RECORD =       If extracting sweeps, you must specify what test record the audio was captured
                    from.  Supported records are STR100, TRS1007 (CA or JVC), and TRS1005. 
                    
plotstyle =         1 - traditional
                    2 - dual axis (twinx)
                    3 - dual plot FR and distortion
                    4 - dual plot FR zoom and dual axis (twinx)
                    5 - small plot FR only

riaamode =          0 - off
                    1 - bass emphasis
                    2 - trebel de-emphasis
                    3 - both

riaainv =           0 - disable
                    1 - inverse RIAA EQ per riaamode setting

str100 =            0 - disable
                    1 - enable 6dB/oct correction from 500Hz to 40Hz

xg7001 =            0 - disable
                    1 - custom bass filter for Denon XG-7001 sweep (@stereoplay filter)

normalize =         Frequency in Hz to set as 0dB in the plot

file0norm =         0 - normalize both files independently
                    1 - normalize both files to file 0 level

onekfstart =        0 - disable
                    1 - start plot from 1kHz

endf =              0 - highest frequency to plot
               

'''

swversion = "18.0"



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



#edit user parameters



INPUT_FILE_0 = 'myfirstwavfile.wav'
INPUT_FILE_1 = 'mysecondwavfile.wav'

SPLIT_INPUT_FILE = 0
SAVE_SPLIT_FILES = 0

TEST_RECORD = 'STR100'  # Options: TRS1007, TRS1005, STR100

infoline = 'Cart / Load / Record'

equipinfo = 'Arm -> Phonostage -> ADC'

plotstyle = 4
plotdataout = 0
roundlvl = 1

riaamode = 2
riaainv = 1
str100 = 0
xg7001 = 0

normalize = 1000
file0norm = 0
onekfstart = 0
endf = 20000

ovdylim = 0
ovdylimvalue = [-5,5]


#end Edit

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)
fh = logging.StreamHandler()
fh_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)
logger.propagate = False


fileopenidx = 0

# Write Output WAV File
def write_file(output_file, data, Fs):
    write(output_file, Fs, data)

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


def createplotdata(insig, Fs):
    fout = []
    aout = []
    foutx = []
    aoutx = []
    fout2 = []
    aout2 = []
    fout3 = []
    aout3 = []
    global norm

    def interpolate(f, a, minf, maxf, fstep):
        f_out = []
        a_out = []
        amp = 0
        count = 0
        for x in range(minf,(maxf)+1,fstep):
            for y in range(0,len(f)):
                if f[y] == x:
                    amp = amp + a[y]
                    count = count + 1
            if count != 0:
                f_out.append(x)
                a_out.append(20*np.log10(amp/count))
            amp = 0
            count = 0
        return f_out, a_out

 
    def rfft(insig, Fs, minf, maxf, fstep):
        freq = []
        amp = []
        freqx = []
        ampx = []
        freq2h = []
        amp2h = []
        freq3h = []
        amp3h = []

        F = int(Fs/fstep)
        win = ft_window(F)

        if chinfile == 1:
            for x in range(0,len(insig)-F,F):
                y = abs(np.fft.rfft(insig[x:x+F]*win))
                f = np.argmax(y) #use largest bin
                if f >=minf/fstep and f <=maxf/fstep:
                    freq.append(f*fstep)
                    amp.append(y[f])
                if 2*f<F/2-2 and f > minf/fstep and f < maxf/fstep:
                    f2 = np.argmax(y[(2*f)-2:(2*f)+2])
                    freq2h.append(f*fstep)
                    amp2h.append(y[2*f-2+f2])
                if 3*f<F/2-2 and f > minf/fstep and f < maxf/fstep:
                    f3 = np.argmax(y[(3*f)-2:(3*f)+2])
                    freq3h.append(f*fstep)
                    amp3h.append(y[3*f-2+f3])


        else:
            for x in range(0,len(insig[0])-F,F):
                y0 = abs(np.fft.rfft(insig[0,x:x+F]*win))
                y1 = abs(np.fft.rfft(insig[1,x:x+F]*win))
                f0 = np.argmax(y0) #use largest bin
                f1 = np.argmax(y1) #use largest bin
                if f0 >=minf/fstep and f0 <=maxf/fstep:
                    freq.append(f0*fstep)
                    freqx.append(f1*fstep)
                    amp.append(y0[f0])
                    ampx.append(y1[f1])
                if 2*f0<F/2-2 and f0 > minf/fstep and f0 < maxf/fstep:
                    f2 = np.argmax(y0[(2*f0)-2:(2*f0)+2])
                    freq2h.append(f0*fstep)
                    amp2h.append(y0[2*f0-2+f2])
                if 3*f0<F/2-2 and f0 > minf/fstep and f0 < maxf/fstep:
                    f3 = np.argmax(y0[(3*f0)-2:(3*f0)+2])
                    freq3h.append(f0*fstep)
                    amp3h.append(y0[3*f0-2+f3])

        return freq, amp, freqx, ampx, freq2h, amp2h, freq3h, amp3h


    def normstr100(f, a):
        fmin = 40
        fmax = 500
        slope = -6.02
        for x in range(find_nearest(f, fmin), (find_nearest(f, fmax))):
            a[x] = a[x] + 20*np.log10(1*((f[x])/fmax)**((slope/20)/np.log10(2)))
        return a


    def chunk(insig, Fs, fmin, fmax, step, offset):
        f, a, fx, ax, f2, a2, f3, a3 = rfft(insig, Fs, fmin, fmax, step)
        f, a = interpolate(f, a, fmin, fmax, step)
        fx, ax = interpolate(fx, ax, fmin, fmax, step)
        f2, a2 = interpolate(f2, a2, fmin, fmax, step)
        f3, a3 = interpolate(f3, a3, fmin, fmax, step)
        a = [x - offset for x in a]
        ax = [x - offset for x in ax]
        a2 = [x - offset for x in a2]
        a3 = [x - offset for x in a3]

        return f, a, fx, ax, f2, a2, f3, a3
 

    def concat(f, a, fx, ax, f2, a2, f3, a3, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3):
        fout = fout + f
        aout = aout + a
        foutx = foutx + fx
        aoutx = aoutx + ax
        fout2 = fout2 + f2
        aout2 = aout2 + a2
        fout3 = fout3 + f3
        aout3 = aout3 + a3

        return fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3

 
    if onekfstart == 0:
        f, a, fx, ax, f2, a2, f3, a3 = chunk(insig, Fs, 20, 45, 5, 26.03)
        fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = concat(f, a, fx, ax, f2, a2, f3, a3, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)

        f, a, fx, ax, f2, a2, f3, a3 = chunk(insig, Fs, 50, 90, 10, 19.995)
        fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = concat(f, a, fx, ax, f2, a2, f3, a3, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)

        f, a, fx, ax, f2, a2, f3, a3 = chunk(insig, Fs, 100, 980, 20, 13.99)
        fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = concat(f, a, fx, ax, f2, a2, f3, a3, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)

    f, a, fx, ax, f2, a2, f3, a3 = chunk(insig, Fs, 1000, endf, 100, 0)
    fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = concat(f, a, fx, ax, f2, a2, f3, a3, fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)

    if str100 == 1:
        aout = normstr100(fout, aout)
        aout2 = normstr100(fout2, aout2)
        aout3 = normstr100(fout3, aout3)
        if chinfile == 2:
            aoutx = normstr100(foutx, aoutx)

    if file0norm == 1 and fileopenidx == 1:
        i = find_nearest(fout, normalize)
        norm = aout[i]
    elif file0norm == 0:
        i = find_nearest(fout, normalize)
        norm = aout[i]

    aout = aout-norm #amplitude is in dB so normalize by subtraction at [i]
    aoutx = aoutx-norm
    aout2 = aout2-norm
    aout3 = aout3-norm
 
    sos = iirfilter(3,.5, btype='lowpass', output='sos') #filter some noise
    aout = sosfiltfilt(sos,aout)
    aout2 = sosfiltfilt(sos,aout2)
    aout3 = sosfiltfilt(sos,aout3)

    if chinfile == 2 and len(aoutx) >1:
        aoutx = sosfiltfilt(sos,aoutx)

    return fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3


def ordersignal(sig, Fs):
    F = int(Fs/100)
    win = ft_window(F)

    if chinfile == 1:
        y = abs(np.fft.rfft(sig[0:F]*win))
        minf = np.argmax(y)
        y = abs(np.fft.rfft(sig[len(sig)-F:len(sig)]*win))
        maxf = np.argmax(y)
    else:
        y = abs(np.fft.rfft(sig[0,0:F]*win))
        minf = np.argmax(y)
        y = abs(np.fft.rfft(sig[0][len(sig[0])-F:len(sig[0])]*win))
        maxf = np.argmax(y)

    if maxf < minf:
        maxf,minf = minf,maxf
        sig = np.flipud(sig)
 
    return sig, minf, maxf


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


def normxg7001(sig, Fs):
    if Fs == 96000:
        b = [1.0080900, -0.9917285, 0]
        a = [1, -0.9998364, 0]
        sig = signal.lfilter(b,a,sig)
    return sig


def get_audio(input_file, split_input_file=0, test_record=None, save_split_files=0):
    global chinfile
    global fileopenidx
    chinfile = 1

    logger.info(f"Reading: {input_file}")
    Fs, audio = read(input_file)
    logger.debug(f"WavFileWarning raised")

    logger.info(f"Sample Rate: {Fs}")

    if Fs <96000:
        logger.info(f"Resampling to 96000")
        audio = resample(audio, int(len(audio) * 96000 / Fs))
        Fs = 96000

    if split_input_file == 1:
        logger.info(f"Extracting sweeps from audio files...")
        chinfile = 2
        audio, audio_2 = slice_audio(audio, Fs, test_record)

        if save_split_files == 1:

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

    if riaamode != 0:
        audio = riaaiir(audio, Fs, riaamode, riaainv)
        try:
            audio_2 = riaaiir(audio_2, Fs, riaamode, riaainv)
        except NameError:
            audio_2 = None

    if xg7001 == 1:
        audio = normxg7001(audio, Fs)
        try:
            audio_2 = normxg7001(audio_2, Fs)
        except NameError:
            audio_2 = None

    if len(audio.shape) == 2:
        chinfile = 2

    audio, minf, maxf = ordersignal(audio, Fs)
    
    logger.info(f"Sweep minimum frequency: {minf * 100:.0f}Hz")
    logger.info(f"Sweep maximum frequency: {maxf * 100:.0f}Hz")
   
    fileopenidx +=1
 
    return audio, audio_2, Fs, minf, maxf


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
        ie = int(start_sample + (12 * Fs))  # End 12s after

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
        logger.debug(f"Sample Offset Start: {sample_offset_start}, Sample Offset End: {sample_offset_end}")
        logger.debug(f"End Sample (Relative Index): {end_sample - sample_offset_start}")
        
        return end_sample


    # Test record parameters
    record_params = {
        'TRS1007': {'sweep_offset': 74, 'sweep_end_min': 48, 'sweep_end_max': 52, 'sweep_start_detect': 0},
        'TRS1005': {'sweep_offset': 32, 'sweep_end_min': 26, 'sweep_end_max': 34, 'sweep_start_detect': 1},
        'STR100': {'sweep_offset': 74, 'sweep_end_min': 63, 'sweep_end_max': 67, 'sweep_start_detect': 0},
    }

    if test_record not in record_params:
        raise ValueError("Invalid test record.")

    params = record_params[test_record]


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





if __name__ == "__main__":

    

    if SPLIT_INPUT_FILE == 1:
        input_sig_1, input_sig_2, Fs, minf, maxf = get_audio(INPUT_FILE_0, SPLIT_INPUT_FILE, TEST_RECORD, SAVE_SPLIT_FILES)
        fo0, ao0, fox0, aox0, fo2h0, ao2h0, fo3h0, ao3h0 = createplotdata(input_sig_1, Fs)

        deltaadj = ao0[find_nearest(fo0, normalize)]
        deltah0 = round((max(ao0 - deltaadj)), roundlvl)
        deltal0 = abs(round((min(ao0 - deltaadj)), roundlvl))

        logger.info(f"Left crosstalk @1kHz: {aox0[find_nearest(fox0, 1000)]:.2f}dB")

        fo1, ao1, fox1, aox1, fo2h1, ao2h1, fo3h1, ao3h1 = createplotdata(input_sig_2, Fs)
 
        deltaadj = ao1[find_nearest(fo1, normalize)]
        deltah1 = round((max(ao1 - deltaadj)), roundlvl)
        deltal1 = abs(round((min(ao1 - deltaadj)), roundlvl))

        logger.info(f"Right crosstalk @1kHz: {aox1[find_nearest(fox1, 1000)]:.2f}dB")

        INPUT_FILE_1 = 'x'


    else:


        input_sig, _, Fs, minf, maxf = get_audio(INPUT_FILE_0)
        fo0, ao0, fox0, aox0, fo2h0, ao2h0, fo3h0, ao3h0 = createplotdata(input_sig, Fs)

        deltaadj = ao0[find_nearest(fo0, normalize)]
        deltah0 = round((max(ao0 - deltaadj)), roundlvl)
        deltal0 = abs(round((min(ao0 - deltaadj)), roundlvl))

        if aox0.size > 0:
            logger.info(f"Left crosstalk @1kHz: {aox0[find_nearest(fox0, 1000)]:.2f}dB")


        if INPUT_FILE_1:
            input_sig, _, Fs, minf, maxf = get_audio(INPUT_FILE_1)
            fo1, ao1, fox1, aox1, fo2h1, ao2h1, fo3h1, ao3h1 = createplotdata(input_sig, Fs)
     
            deltaadj = ao1[find_nearest(fo1, normalize)]
            deltah1 = round((max(ao1 - deltaadj)), roundlvl)
            deltal1 = abs(round((min(ao1 - deltaadj)), roundlvl))

            if aox1.size > 0:
                logger.info(f"Right crosstalk @1kHz: {aox1[find_nearest(fox1, 1000)]:.2f}dB")


    if plotdataout == 1:

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

    if plotstyle == 1:
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

        if ovdylim == 1:
            axs[0].set_ylim(*ovdylimvalue)
 

    if plotstyle == 2:
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
 
        if ovdylim == 1:
            axs[0].set_ylim(*ovdylimvalue)

 
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


    if plotstyle == 3:
        fig, axs = plt.subplots(2, 1, sharex=True, figsize=(14,6))

        axs[0].set_ylim(-5,5)

        if INPUT_FILE_1:
            if (min(chain(ao0, ao1)) <-5) or (max(chain(ao0, ao1)) >5):
                axs[0].autoscale(enable=True, axis='y')
        elif (min(ao0) <-5) or (max(ao0) >5):
                axs[0].autoscale(enable=True, axis='y')

        if ovdylim == 1:
            axs[0].set_ylim(*ovdylimvalue)

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


    if plotstyle == 4:
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
 
        if ovdylim == 1:
            axs[1].set_ylim(*ovdylimvalue)

 
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

        if ovdylim == 1:
            axs[0].set_ylim(*ovdylimvalue)

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

    if plotstyle == 5:
        fig, axs = plt.subplots(1, 1, figsize=(14,3))
        axs = np.ravel([axs])

        axs[0].set_ylim(-5,5)

        if INPUT_FILE_1:
            if (min(chain(ao0, ao1)) <-5) or (max(chain(ao0, ao1)) >5):
                axs[0].autoscale(enable=True, axis='y')
        elif (min(ao0) <-5) or (max(ao0) >5):
                axs[0].autoscale(enable=True, axis='y')

        if ovdylim == 1:
            axs[0].set_ylim(*ovdylimvalue)

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
 
        if file0norm == 1:
            if  not (plotstyle == 3 and i != 0):
                ax.axline((normalize, 0), (normalize, 1), color = 'm', lw = 1)
        elif file0norm == 0:
            if not (plotstyle == 3 and i != 0):
                ax.plot(normalize, 0, marker = 'x', color = 'm')
        
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

    axs[0].set_title(infoline + "\n", fontsize=16)


    now = datetime.now()

    if INPUT_FILE_1:
        plt.figtext(.17, .118, "SJPlot v" + swversion + "\n" + INPUT_FILE_0 + "\n" + INPUT_FILE_1 + "\n" + \
            now.strftime("%b %d, %Y %H:%M"), fontsize=6)
    else:
        plt.figtext(.17, .118, "SJPlot v" + swversion + "\n" + INPUT_FILE_0 + "\n" + \
            now.strftime("%b %d, %Y %H:%M"), fontsize=6)

    plt.figtext(.125, 0, equipinfo, alpha=.75, fontsize=8)
     
    plt.savefig(infoline.replace(' / ', '_') +'.png', bbox_inches='tight', pad_inches=.5, dpi=96)

    plt.show()

    logger.info(f"Done!")
