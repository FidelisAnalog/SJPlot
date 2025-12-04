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
from itertools import chain
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import numpy as np
import os
import logging

import io

# Import from myhifi_lib
from myhifi_lib import (
    extract_sweeps,
    analyze_sweep,
    normalize_to_frequency,
    ordersignal,
    find_nearest,
    ft_window,
    riaaiir,
    normxg7001,
    normstr100,
    apply_frequency_slope,
    TEST_RECORD_PARAMS,
    # Visualization
    AUDIO_STYLE,
    DualColorHandler,
    format_freq,
    setup_rcparams,
    setup_axis_grid,
    setup_axis_ticks,
    setup_axis_xlim,
    setup_minor_tick_labels,
    calculate_xlim_with_margin,
    set_ylim_tight,
    set_ylim_cascade,
    set_ylim_from_data,
    create_freq_response_figure,
    add_watermark,
    add_normalize_marker,
    add_delta_annotation,
    add_title,
    add_footer_text,
    save_figure,
    figure_to_buffer,
    close_figure,
)


__version__ = "18.6.6"


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


def get_config(config_path=None):
    """
    Load configuration from JSON file.
    
    Config structure:
    {
      "plot_info": "",
      "equip_info": "",
      "author": "",
      
      "files": [
        {"path": "recording.wav", "label": ""}
      ],
      
      "mode": "standard",
      "style": 4,
      "dimensions": ["fundamental", "crosstalk", "h2", "h3"],
      
      "extract_sweeps": false,
      "extract_channel": "both",
      "test_record": "STR100",
      
      "normalize": 1000,
      "normalize_mode": "relative",
      
      "start_f": null,
      "end_f": null,
      "smoothing": 0.5,
      "override_ylim": null,
      
      "riaa_mode": 0,
      "riaa_inverse": false,
      "str100": false,
      "xg7001": false,
      
      "plot_data_out": false,
      "log_level": "info"
    }
    """
    import json
    
    defaults = {
        "plot_info": "Cart / Load / Record",
        "equip_info": "Arm -> Phonostage -> ADC",
        "author": "",
        
        "files": [],
        
        "mode": "standard",
        "style": 4,
        "dimensions": ["fundamental", "crosstalk", "h2", "h3"],
        
        "extract_sweeps": False,
        "extract_channel": "both",
        "test_record": "STR100",
        
        "normalize": 1000,
        "normalize_mode": "relative",
        
        "start_f": None,
        "end_f": None,
        "smoothing": 0.5,
        "override_ylim": None,
        
        "riaa_mode": 0,
        "riaa_inverse": False,
        "str100": False,
        "xg7001": False,
        
        "plot_data_out": False,
        "log_level": "info",
    }
    
    config = {**defaults}
    
    # Load from JSON file if provided
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            file_config = json.load(f)
        config.update(file_config)
        logger.info(f"Loaded configuration from {config_path}")
    
    # Check for web configuration
    try:
        from js import window
        if hasattr(window, 'js_config'):
            web_config = window.js_config.to_py()
            logger.info("Applying web configuration overrides")
            config.update(web_config)
    except ImportError:
        pass
    
    # Auto-set str100/xg7001 from test_record
    if config["test_record"].upper() == "STR100":
        config["str100"] = True
    if config["test_record"].upper() == "XG7001":
        config["xg7001"] = True
    
    return config




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
        # Format values: frequency as integer, amplitudes to 2 decimal places
        f_out = f'{int(f)}' if f != '' else ''
        a_out = f'{a:.2f}' if a != '' else ''
        ax_out = f'{ax:.2f}' if ax != '' else ''
        a2_out = f'{a2:.2f}' if a2 != '' else ''
        a3_out = f'{a3:.2f}' if a3 != '' else ''
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


def load_file_data(file_input, environment='standalone'):
    """
    Load audio file data from path (standalone) or bytes (web).
    
    Returns:
        tuple: (audio_data, sample_rate)
    """
    if environment == 'web':
        # file_input is bytes
        audio_buffer = io.BytesIO(file_input)
        Fs, data = read(audio_buffer)
    else:
        # file_input is path string
        Fs, data = read(file_input)
    
    # Convert to float
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    
    return data, Fs


def process_file(file_path, file_bytes, label, config, environment='standalone'):
    """
    Process a single file through the analysis pipeline.
    
    Returns list of result dicts (one per channel analyzed):
    [
        {
            'label': str,
            'channel': 'left' or 'right' or None,
            'data': analyze_sweep result dict
        },
        ...
    ]
    """
    from scipy.signal import resample
    
    # Load file
    if environment == 'web':
        data, Fs = load_file_data(file_bytes, environment)
    else:
        data, Fs = load_file_data(file_path, environment)
    
    # Resample to 96kHz if needed
    target_fs = 96000
    if Fs != target_fs:
        if len(data.shape) == 2:
            num_samples = int(data.shape[0] * target_fs / Fs)
            data = np.column_stack([
                resample(data[:, 0], num_samples),
                resample(data[:, 1], num_samples)
            ])
        else:
            num_samples = int(len(data) * target_fs / Fs)
            data = resample(data, num_samples)
        Fs = target_fs
    
    results = []
    
    if config['extract_sweeps']:
        # Split stereo for extraction
        if len(data.shape) == 2:
            left = data[:, 0]
            right = data[:, 1]
        else:
            raise ValueError("Extract sweeps requires stereo input")
        
        # Extract sweeps
        extraction = extract_sweeps(left, right, Fs, config['test_record'])
        
        # Determine which channels to process
        channels_to_process = []
        if config['extract_channel'] in ('left', 'both'):
            channels_to_process.append(('left', extraction['left']))
        if config['extract_channel'] in ('right', 'both'):
            channels_to_process.append(('right', extraction['right']))
        
        for channel_name, sweep_data in channels_to_process:
            # Transpose for analyze_sweep (expects channels as first dim)
            signal = sweep_data.T
            
            # Apply RIAA if requested
            if config['riaa_mode'] > 0:
                signal[0] = riaaiir(signal[0], Fs, config['riaa_mode'], config['riaa_inverse'])
                if signal.shape[0] > 1:
                    signal[1] = riaaiir(signal[1], Fs, config['riaa_mode'], config['riaa_inverse'])
            
            # Apply XG7001 if requested
            if config['xg7001']:
                signal[0] = normxg7001(signal[0], Fs)
                if signal.shape[0] > 1:
                    signal[1] = normxg7001(signal[1], Fs)
            
            # Analyze
            result = analyze_sweep(signal, Fs, 
                                   start_f=config['start_f'], 
                                   end_f=config['end_f'],
                                   smoothing=config['smoothing'])
            
            # Apply STR100 correction
            if config['str100']:
                result['amp'] = normstr100(result['freq'], result['amp'])
                if len(result['harmonic2_amp']) > 0:
                    result['harmonic2_amp'] = normstr100(result['harmonic2_freq'], result['harmonic2_amp'])
                if len(result['harmonic3_amp']) > 0:
                    result['harmonic3_amp'] = normstr100(result['harmonic3_freq'], result['harmonic3_amp'])
                if len(result['crosstalk_amp']) > 0:
                    result['crosstalk_amp'] = normstr100(result['crosstalk_freq'], result['crosstalk_amp'])
            
            # Convert to numpy arrays
            for key in ['amp', 'crosstalk_amp', 'harmonic2_amp', 'harmonic3_amp']:
                if len(result[key]) > 0:
                    result[key] = np.asarray(result[key])
            
            results.append({
                'label': label,
                'channel': channel_name,
                'data': result,
                'Fs': Fs
            })
    
    else:
        # Pre-trimmed file - analyze directly
        if len(data.shape) == 2:
            signal = data.T  # (samples, channels) -> (channels, samples)
        else:
            signal = np.expand_dims(data, axis=0)
        
        # Apply RIAA if requested
        if config['riaa_mode'] > 0:
            signal[0] = riaaiir(signal[0], Fs, config['riaa_mode'], config['riaa_inverse'])
            if signal.shape[0] > 1:
                signal[1] = riaaiir(signal[1], Fs, config['riaa_mode'], config['riaa_inverse'])
        
        # Apply XG7001 if requested
        if config['xg7001']:
            signal[0] = normxg7001(signal[0], Fs)
            if signal.shape[0] > 1:
                signal[1] = normxg7001(signal[1], Fs)
        
        # Analyze
        result = analyze_sweep(signal, Fs,
                               start_f=config['start_f'],
                               end_f=config['end_f'],
                               smoothing=config['smoothing'])
        
        # Apply STR100 correction
        if config['str100']:
            result['amp'] = normstr100(result['freq'], result['amp'])
            if len(result['harmonic2_amp']) > 0:
                result['harmonic2_amp'] = normstr100(result['harmonic2_freq'], result['harmonic2_amp'])
            if len(result['harmonic3_amp']) > 0:
                result['harmonic3_amp'] = normstr100(result['harmonic3_freq'], result['harmonic3_amp'])
            if len(result['crosstalk_amp']) > 0:
                result['crosstalk_amp'] = normstr100(result['crosstalk_freq'], result['crosstalk_amp'])
        
        # Convert to numpy arrays
        for key in ['amp', 'crosstalk_amp', 'harmonic2_amp', 'harmonic3_amp']:
            if len(result[key]) > 0:
                result[key] = np.asarray(result[key])
        
        results.append({
            'label': label,
            'channel': None,  # Not from extraction
            'data': result,
            'Fs': Fs
        })
    
    return results


def normalize_results(results, normalize_freq, normalize_mode):
    """
    Apply normalization to all results.
    
    normalize_mode:
        'relative': All files normalized to FIRST file's level at normalize_freq
        'absolute': Each file normalized to its OWN level at normalize_freq
    """
    if normalize_freq is None:
        return results
    
    first_file_offset = None
    
    for result in results:
        data = result['data']
        
        # Find offset at normalize frequency
        idx = find_nearest(data['freq'], normalize_freq)
        this_offset = data['amp'][idx]
        
        # Determine which offset to use
        if normalize_mode == 'relative':
            # Use first file's offset for all files
            if first_file_offset is None:
                first_file_offset = this_offset
            norm_offset = first_file_offset
        else:
            # 'absolute' - each file uses its own offset
            norm_offset = this_offset
        
        # Apply offset to all amplitude arrays
        data['amp'] = np.asarray(data['amp']) - norm_offset
        
        if len(data['crosstalk_amp']) > 0:
            data['crosstalk_amp'] = np.asarray(data['crosstalk_amp']) - norm_offset
        if len(data['harmonic2_amp']) > 0:
            data['harmonic2_amp'] = np.asarray(data['harmonic2_amp']) - norm_offset
        if len(data['harmonic3_amp']) > 0:
            data['harmonic3_amp'] = np.asarray(data['harmonic3_amp']) - norm_offset
    
    return results


def calculate_delta(amp_data, round_level=1):
    """Calculate positive and negative deviation from 0dB."""
    amp_array = np.asarray(amp_data)
    delta_high = round(max(amp_array), round_level)
    delta_low = round(abs(min(amp_array)), round_level)
    return delta_high, delta_low


def plot_results(results, config, environment='standalone'):
    """
    Create plot from analyzed results.
    
    Handles both standard and comparison modes.
    
    Style layouts:
        1: single axis, all dimensions
        2: single + twin, fundamental/crosstalk on main, h2/h3 on twin
        3: dual panel, L on top, R on bottom (fundamental only)
        4: dual + twin, top=fundamental overview, bottom=all dimensions with twin
        5: compact, fundamental only
    """
    from matplotlib.ticker import FuncFormatter
    
    mode = config['mode']
    style = config['style']
    
    colors = AUDIO_STYLE['colors']
    lines = AUDIO_STYLE['lines']
    
    # Dimensions: locked by style for standard mode, user choice for comparison
    style_dimensions = {
        1: ['fundamental', 'crosstalk', 'h2', 'h3'],
        2: ['fundamental', 'crosstalk', 'h2', 'h3'],
        3: ['fundamental'],
        4: ['fundamental', 'crosstalk', 'h2', 'h3'],
        5: ['fundamental'],
    }
    
    if mode == 'standard':
        dimensions = style_dimensions.get(style, ['fundamental'])
    else:
        dimensions = config['dimensions']
    
    setup_rcparams()
    
    # Determine layout based on style
    if style == 1:
        layout = 'single'
        has_twin = False
    elif style == 2:
        layout = 'single_twin'
        has_twin = True
    elif style == 3:
        layout = 'dual'
        has_twin = False
    elif style == 4:
        layout = 'dual_twin'
        has_twin = True
    elif style == 5:
        layout = 'compact'
        has_twin = False
    else:
        layout = 'single'
        has_twin = False
    
    # Create figure
    fig, axes = create_freq_response_figure(layout)
    
    # Get axes based on layout
    if layout in ('single', 'single_twin', 'compact'):
        ax_main = axes['main']
        ax_bottom = None
        axs = np.array([ax_main])
    else:
        ax_top = axes['top']
        ax_bottom = axes['bottom']
        ax_main = ax_top  # For title etc
        axs = np.array([ax_top, ax_bottom])
    
    # Get twin axis if present
    ax_twin = axes.get('twin', None)
    
    # Determine where harmonics go (for non-dual layouts)
    ax_harmonics = ax_twin if has_twin else ax_main
    
    # Collect all frequency/amplitude data for axis limits
    all_freq = []
    all_amp = []
    
    if mode == 'standard':
        result0 = results[0]['data']
        all_freq.extend(result0['freq'])
        all_amp.extend(result0['amp'])
        
        result1 = results[1]['data'] if len(results) > 1 else None
        if result1:
            all_freq.extend(result1['freq'])
            all_amp.extend(result1['amp'])
        
        # Handle different style layouts
        if style == 3:
            # Style 3: L on top, R on bottom (fundamental only)
            ax_top.semilogx(result0['freq'], result0['amp'],
                          color=colors['left'], label='Freq Response',
                          **lines['fundamental'])
            
            if result1:
                ax_bottom.semilogx(result1['freq'], result1['amp'],
                                  color=colors['right'], label='Freq Response',
                                  **lines['fundamental'])
            
            # Set y limits for both panels
            set_ylim_tight(ax_top, result0['amp'], override=config['override_ylim'])
            if result1:
                set_ylim_tight(ax_bottom, result1['amp'], override=config['override_ylim'])
            
            # Legends
            ax_top.legend(loc=4)
            if result1:
                ax_bottom.legend(loc=4)
            
            # Delta annotations
            delta_high, delta_low = calculate_delta(result0['amp'])
            add_delta_annotation(ax_top, delta_high, delta_low,
                               result0['freq'], result0['amp'], channel='left')
            if result1:
                delta_high, delta_low = calculate_delta(result1['amp'])
                add_delta_annotation(ax_bottom, delta_high, delta_low,
                                   result1['freq'], result1['amp'], channel='right')
        
        elif style == 4:
            # Style 4: top=fundamental overview, bottom=all dimensions with twin
            # Top panel - fundamental only
            ax_top.semilogx(result0['freq'], result0['amp'],
                          color=colors['left'], label='Freq Response',
                          **lines['fundamental'])
            if result1:
                ax_top.semilogx(result1['freq'], result1['amp'],
                              color=colors['right'], label='Freq Response',
                              **lines['fundamental'])
            
            # Bottom panel - fundamental + crosstalk on main axis
            ax_bottom.semilogx(result0['freq'], result0['amp'],
                              color=colors['left'], label='Freq Response',
                              **lines['fundamental'])
            if 'crosstalk' in dimensions and len(result0['crosstalk_amp']) > 0:
                ax_bottom.semilogx(result0['crosstalk_freq'], result0['crosstalk_amp'],
                                  color=colors['left'], label='Crosstalk',
                                  **lines['crosstalk'])
            
            # Harmonics on twin axis
            if 'h2' in dimensions and len(result0['harmonic2_amp']) > 0:
                ax_twin.semilogx(result0['harmonic2_freq'], result0['harmonic2_amp'],
                               color=colors['left_h2'], label='2nd Harmonic',
                               **lines['harmonic'])
            if 'h3' in dimensions and len(result0['harmonic3_amp']) > 0:
                ax_twin.semilogx(result0['harmonic3_freq'], result0['harmonic3_amp'],
                               color=colors['left_h3'], label='3rd Harmonic',
                               **lines['harmonic'])
            
            if result1:
                ax_bottom.semilogx(result1['freq'], result1['amp'],
                                  color=colors['right'], label='Freq Response',
                                  **lines['fundamental'])
                if 'crosstalk' in dimensions and len(result1['crosstalk_amp']) > 0:
                    ax_bottom.semilogx(result1['crosstalk_freq'], result1['crosstalk_amp'],
                                      color=colors['right'], label='Crosstalk',
                                      **lines['crosstalk'])
                
                if 'h2' in dimensions and len(result1['harmonic2_amp']) > 0:
                    ax_twin.semilogx(result1['harmonic2_freq'], result1['harmonic2_amp'],
                                   color=colors['right_h2'], label='2nd Harmonic',
                                   **lines['harmonic'])
                if 'h3' in dimensions and len(result1['harmonic3_amp']) > 0:
                    ax_twin.semilogx(result1['harmonic3_freq'], result1['harmonic3_amp'],
                                   color=colors['right_h3'], label='3rd Harmonic',
                                   **lines['harmonic'])
            
            # Y limits
            set_ylim_tight(ax_top, all_amp, override=config['override_ylim'])
            
            # Bottom panel limits - cascade or crosstalk-driven
            if len(result0['crosstalk_amp']) > 0:
                xtalk_data = list(result0['crosstalk_amp'])
                if result1 and len(result1['crosstalk_amp']) > 0:
                    xtalk_data.extend(result1['crosstalk_amp'])
                set_ylim_from_data(ax_bottom, xtalk_data + all_amp, override=config['override_ylim'])
            else:
                set_ylim_cascade(ax_bottom, all_amp, override=config['override_ylim'])
            
            # Align twin axis
            from myhifi_lib.visualization import align_yaxis
            new_lim1, new_lim2 = align_yaxis(ax_bottom, ax_twin)
            ax_bottom.set_ylim(new_lim1)
            ax_twin.set_ylim(new_lim2)
            
            # Legends
            if result1:
                # Top panel legend
                ax_top.legend([(colors['left'], "-", colors['right'], "-")],
                            ['Freq Response'],
                            handler_map={tuple: DualColorHandler()}, loc=4)
                
                # Bottom panel legend
                legend_handles = [(colors['left'], "-", colors['right'], "-")]
                legend_labels = ['Freq Response']
                
                if 'crosstalk' in dimensions:
                    legend_handles.append((colors['left'], lines['crosstalk']['linestyle'],
                                         colors['right'], lines['crosstalk']['linestyle']))
                    legend_labels.append('Crosstalk')
                if 'h2' in dimensions:
                    legend_handles.append((colors['left_h2'], "-", colors['right_h2'], "-"))
                    legend_labels.append('2nd Harmonic')
                if 'h3' in dimensions:
                    legend_handles.append((colors['left_h3'], "-", colors['right_h3'], "-"))
                    legend_labels.append('3rd Harmonic')
                
                ax_bottom.legend(legend_handles, legend_labels,
                               handler_map={tuple: DualColorHandler()}, loc=4)
            else:
                ax_top.legend(loc=4)
                # Combine main and twin legends
                lines1, labels1 = ax_bottom.get_legend_handles_labels()
                lines2, labels2 = ax_twin.get_legend_handles_labels()
                ax_bottom.legend(lines1 + lines2, labels1 + labels2, loc=4)
            
            # Delta annotations on top panel
            delta_high, delta_low = calculate_delta(result0['amp'])
            add_delta_annotation(ax_top, delta_high, delta_low,
                               result0['freq'], result0['amp'], channel='left')
            if result1:
                delta_high, delta_low = calculate_delta(result1['amp'])
                add_delta_annotation(ax_top, delta_high, delta_low,
                                   result0['freq'], result0['amp'],
                                   channel='right', offset_y=-14.5)
        
        else:
            # Styles 1, 2, 5 - single panel (with or without twin)
            ax_main.semilogx(result0['freq'], result0['amp'],
                           color=colors['left'], label='Freq Response',
                           **lines['fundamental'])
            
            if 'crosstalk' in dimensions and len(result0['crosstalk_amp']) > 0:
                ax_main.semilogx(result0['crosstalk_freq'], result0['crosstalk_amp'],
                               color=colors['left'], label='Crosstalk',
                               **lines['crosstalk'])
            
            if 'h2' in dimensions and len(result0['harmonic2_amp']) > 0:
                ax_harmonics.semilogx(result0['harmonic2_freq'], result0['harmonic2_amp'],
                               color=colors['left_h2'], label='2nd Harmonic',
                               **lines['harmonic'])
            if 'h3' in dimensions and len(result0['harmonic3_amp']) > 0:
                ax_harmonics.semilogx(result0['harmonic3_freq'], result0['harmonic3_amp'],
                               color=colors['left_h3'], label='3rd Harmonic',
                               **lines['harmonic'])
            
            if result1:
                ax_main.semilogx(result1['freq'], result1['amp'],
                               color=colors['right'], label='Freq Response',
                               **lines['fundamental'])
                
                if 'crosstalk' in dimensions and len(result1['crosstalk_amp']) > 0:
                    ax_main.semilogx(result1['crosstalk_freq'], result1['crosstalk_amp'],
                                   color=colors['right'], label='Crosstalk',
                                   **lines['crosstalk'])
                
                if 'h2' in dimensions and len(result1['harmonic2_amp']) > 0:
                    ax_harmonics.semilogx(result1['harmonic2_freq'], result1['harmonic2_amp'],
                                   color=colors['right_h2'], label='2nd Harmonic',
                                   **lines['harmonic'])
                if 'h3' in dimensions and len(result1['harmonic3_amp']) > 0:
                    ax_harmonics.semilogx(result1['harmonic3_freq'], result1['harmonic3_amp'],
                                   color=colors['right_h3'], label='3rd Harmonic',
                                   **lines['harmonic'])
                
                # Legend with DualColorHandler
                legend_handles = [(colors['left'], "-", colors['right'], "-")]
                legend_labels = ['Freq Response']
                
                if 'crosstalk' in dimensions:
                    legend_handles.append((colors['left'], lines['crosstalk']['linestyle'],
                                         colors['right'], lines['crosstalk']['linestyle']))
                    legend_labels.append('Crosstalk')
                if 'h2' in dimensions:
                    legend_handles.append((colors['left_h2'], "-", colors['right_h2'], "-"))
                    legend_labels.append('2nd Harmonic')
                if 'h3' in dimensions:
                    legend_handles.append((colors['left_h3'], "-", colors['right_h3'], "-"))
                    legend_labels.append('3rd Harmonic')
                
                ax_main.legend(legend_handles, legend_labels,
                             handler_map={tuple: DualColorHandler()}, loc=4)
            else:
                ax_main.legend(loc=4)
            
            # Y limits
            if style == 5:
                set_ylim_tight(ax_main, all_amp, override=config['override_ylim'])
            elif len(result0['crosstalk_amp']) > 0:
                xtalk_data = list(result0['crosstalk_amp'])
                if result1 and len(result1['crosstalk_amp']) > 0:
                    xtalk_data.extend(result1['crosstalk_amp'])
                set_ylim_from_data(ax_main, xtalk_data + all_amp, override=config['override_ylim'])
            else:
                set_ylim_cascade(ax_main, all_amp, override=config['override_ylim'])
            
            # Align twin axis if present
            if ax_twin is not None:
                from myhifi_lib.visualization import align_yaxis
                new_lim1, new_lim2 = align_yaxis(ax_main, ax_twin)
                ax_main.set_ylim(new_lim1)
                ax_twin.set_ylim(new_lim2)
            
            # Delta annotations
            delta_high, delta_low = calculate_delta(result0['amp'])
            add_delta_annotation(ax_main, delta_high, delta_low,
                               result0['freq'], result0['amp'], channel='left')
            if result1:
                delta_high, delta_low = calculate_delta(result1['amp'])
                add_delta_annotation(ax_main, delta_high, delta_low,
                                   result0['freq'], result0['amp'],
                                   channel='right', offset_y=-14.5)
    
    else:
        # Comparison mode: custom labels, default color cycle
        color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
        
        # For dual panel in comparison mode, use same approach as standard
        if style in (3, 4) and ax_bottom is not None:
            # Style 3/4 comparison: could split by some criteria or just use bottom panel
            # For now, put all on bottom panel for comparison
            plot_ax = ax_bottom if style == 4 else ax_main
            ax_harmonics = ax_twin if ax_twin else plot_ax
        else:
            plot_ax = ax_main
            ax_harmonics = ax_twin if ax_twin else ax_main
        
        for i, result_item in enumerate(results):
            result = result_item['data']
            label = result_item['label']
            color = color_cycle[i % len(color_cycle)]
            
            all_freq.extend(result['freq'])
            all_amp.extend(result['amp'])
            
            if 'fundamental' in dimensions:
                plot_ax.semilogx(result['freq'], result['amp'],
                               color=color, label=label,
                               **lines['fundamental'])
            
            if 'crosstalk' in dimensions and len(result['crosstalk_amp']) > 0:
                plot_ax.semilogx(result['crosstalk_freq'], result['crosstalk_amp'],
                               color=color, **lines['crosstalk'])
            
            if 'h2' in dimensions and len(result['harmonic2_amp']) > 0:
                ax_harmonics.semilogx(result['harmonic2_freq'], result['harmonic2_amp'],
                               color=color, linewidth=0.75)
            if 'h3' in dimensions and len(result['harmonic3_amp']) > 0:
                ax_harmonics.semilogx(result['harmonic3_freq'], result['harmonic3_amp'],
                               color=color, linewidth=0.75, alpha=0.7)
        
        # Y limits for comparison
        if config['override_ylim'] is not None:
            plot_ax.set_ylim(config['override_ylim'])
        elif style in (3, 5):
            set_ylim_tight(plot_ax, all_amp)
        else:
            set_ylim_cascade(plot_ax, all_amp)
        
        # Align twin if present
        if ax_twin is not None:
            from myhifi_lib.visualization import align_yaxis
            new_lim1, new_lim2 = align_yaxis(plot_ax, ax_twin)
            plot_ax.set_ylim(new_lim1)
            ax_twin.set_ylim(new_lim2)
        
        # Comparison legend - bottom center
        plot_ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15),
                      ncol=min(len(results), 4))
    
    # X limits (apply to all axes via sharex or manually)
    xlim = calculate_xlim_with_margin(all_freq)
    if xlim:
        ax_main.set_xlim(xlim)
        if ax_bottom is not None:
            ax_bottom.set_xlim(xlim)
    
    # Labels
    if ax_bottom is not None:
        ax_bottom.set_ylabel("Amplitude (dB)")
        ax_bottom.set_xlabel("Frequency (Hz)")
        ax_main.set_ylabel("Amplitude (dB)")
    else:
        ax_main.set_ylabel("Amplitude (dB)")
        ax_main.set_xlabel("Frequency (Hz)")
    
    if ax_twin is not None:
        ax_twin.set_ylabel("Distortion (dB)")
    
    # X-axis tick formatter
    from matplotlib.ticker import FuncFormatter
    for ax in axs:
        ax.set_xticks([20, 50, 100, 500, 1000, 5000, 10000, 20000, 50000, 100000])
        ax.xaxis.set_major_formatter(FuncFormatter(format_freq))
        
        # For narrow frequency ranges, also format minor ticks
        xlim_ax = ax.get_xlim()
        if xlim_ax[0] > 0:
            decades = np.log10(xlim_ax[1] / xlim_ax[0])
            if decades < 2:
                ax.xaxis.set_minor_formatter(FuncFormatter(format_freq))
    
    # Re-apply xlim after setting ticks (set_xticks can expand limits)
    if xlim:
        ax_main.set_xlim(xlim)
        if ax_bottom is not None:
            ax_bottom.set_xlim(xlim)
    
    # Title
    add_title(ax_main, config['plot_info'])
    
    # Footer
    bottom_ax = axs[-1]
    add_footer_text(fig, config['equip_info'], config['author'], bottom_ax)
    
    # Normalization marker
    if config['normalize'] is not None:
        xlim = ax_main.get_xlim()
        if xlim[0] <= config['normalize'] <= xlim[1]:
            for ax in axs:
                if config['normalize_mode'] == 'absolute':
                    add_normalize_marker(ax, config['normalize'], mode='x')
                else:
                    add_normalize_marker(ax, config['normalize'], mode='line')
    
    # Apply GridSpec for dual panel layouts (must be done after all plotting)
    if style in (3, 4):
        from matplotlib.gridspec import GridSpec
        gs = GridSpec(2, 1, height_ratios=[1, 2])
        ax_main.set_position(gs[0].get_position(fig))
        ax_bottom.set_position(gs[1].get_position(fig))
    
    return fig, axs


def main(config_path=None):
    """
    Main entry point using JSON config.
    """
    logger.info(f"SJPlot {__version__}")
    
    # Load config
    config = get_config(config_path)
    
    if config['log_level'].upper() == 'DEBUG':
        logger.setLevel(logging.DEBUG)
    
    environment = get_environment()
    
    # Process all files
    all_results = []
    
    if environment == 'web':
        from js import window
        # Web mode - get file data from JS
        # For now, support files array with js_file0_data, js_file1_data pattern
        # TODO: Extend for n files
        if hasattr(window, 'js_file0_data') and window.js_file0_data:
            file_bytes = bytes(window.js_file0_data.to_py())
            file_info = config['files'][0] if config['files'] else {'path': '', 'label': ''}
            results = process_file(None, file_bytes, file_info.get('label', ''), config, environment)
            all_results.extend(results)
        
        if hasattr(window, 'js_file1_data') and window.js_file1_data:
            file_bytes = bytes(window.js_file1_data.to_py())
            file_info = config['files'][1] if len(config['files']) > 1 else {'path': '', 'label': ''}
            results = process_file(None, file_bytes, file_info.get('label', ''), config, environment)
            all_results.extend(results)
    else:
        # Standalone mode - process each file in config
        for file_info in config['files']:
            results = process_file(file_info['path'], None, file_info.get('label', ''), config, environment)
            all_results.extend(results)
    
    if not all_results:
        logger.error("No files processed")
        return
    
    # Normalize
    all_results = normalize_results(all_results, config['normalize'], config['normalize_mode'])
    
    # Plot
    fig, axs = plot_results(all_results, config, environment)
    
    # Output
    if environment == 'web':
        buf = figure_to_buffer(fig)
        # Send to web frontend
        from js import window
        import base64
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        if hasattr(window, 'updatePlotImage'):
            window.updatePlotImage(img_base64)
    else:
        output_name = config['plot_info'].replace(' / ', '_') + '.png'
        save_figure(fig, output_name)
        logger.info(f"Saved: {output_name}")
        plt.show()
    
    close_figure(fig)
    
    # Output plot data if requested
    if config['plot_data_out']:
        # TODO: Implement for new structure
        pass
    
    logger.info("Done!")


if __name__ == "__main__":
    import sys
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(config_path)
