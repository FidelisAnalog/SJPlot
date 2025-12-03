# SJPlot Signal Processing Pipeline Analysis

## Table of Contents
1. [Overview](#overview)
2. [Pipeline Architecture](#pipeline-architecture)
3. [Data Flow Diagram](#data-flow-diagram)
4. [Stage 1: Audio Input & Sweep Extraction](#stage-1-audio-input--sweep-extraction)
5. [Stage 2: Sweep Detection & Orientation](#stage-2-sweep-detection--orientation)
6. [Stage 3: Pre-Processing Filters](#stage-3-pre-processing-filters)
7. [Stage 4: FFT Analysis & Frequency Response Extraction](#stage-4-fft-analysis--frequency-response-extraction)
8. [Stage 5: Post-Processing & Output](#stage-5-post-processing--output)
9. [Known Issues and Limitations](#known-issues-and-limitations)
10. [Performance Analysis](#performance-analysis)

---

## Overview

SJPlot implements a sophisticated signal processing pipeline for analyzing phono cartridge frequency response from test record sweeps. The pipeline processes audio recordings through multiple stages: file I/O, sweep extraction, orientation detection, optional filtering, multi-resolution FFT analysis, and data export.

**Purpose**: Transform time-domain audio recordings of test record sweeps into frequency-domain amplitude response curves suitable for plotting phono cartridge performance.

**Key Capabilities**:
- Multi-resolution FFT analysis (4 frequency bands with optimal resolution per band)
- Harmonic distortion detection (2nd and 3rd harmonics)
- Stereo/dual-channel support for left/right comparison
- Test record-specific corrections (STR-100, XG7001)
- RIAA filtering (bass, treble, or both)
- Automatic sweep detection and extraction
- Crosstalk measurement
- CSV data export for external analysis

---

## Pipeline Architecture

The signal processing pipeline consists of five major stages:

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: Audio Input & Sweep Extraction                         │
│ ─────────────────────────────────────────────────────────────── │
│ • get_audio(): Read WAV file or receive web upload              │
│ • slice_audio(): Extract left/right sweeps (optonal,            │
│   supported test records only)                                  │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: Sweep Detection & Orientation                          │
│ ─────────────────────────────────────────────────────────────── │
│ • ordersignal(): Detect sweep direction                         │
│ • FFT analysis of start/end to find frequency trend             │
│ • Automatic reversal if sweep is backwards                      │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 3: Pre-Processing Filters (Optional)                      │
│ ─────────────────────────────────────────────────────────────── │
│ • riaaiir(): RIAA equalization (bass, treble, or both,          │
│   and inverse)                                                  │
│ • normxg7001(): XG7001 test record correction                   │
│ • IIR filtering in time domain before FFT analysis              │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 4: FFT Analysis & Frequency Response Extraction           │
│ ─────────────────────────────────────────────────────────────── │
│ • createplotdata(): Core analysis engine                        │
│   ├─ Multi-resolution windowed FFT (4 frequency bands)          │
│   ├─ Peak detection for fundamental frequency                   │
│   ├─ Harmonic extraction (2nd and 3rd)                          │
│   ├─ Binning and averaging for regularization                   │
│   ├─ FFT window size compensation                               │
│   ├─ Low-pass smoothing filter                                  │
│   ├─ Normalization to reference frequency                       │
│   └─ Frequency range filtering                                  │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 5: Post-Processing & Output                               │
│ ─────────────────────────────────────────────────────────────── │
│ • output_plot_data(): Generate CSV export (optional)            │
│ • Crosstalk calculation at 1 kHz                                │
│ • Statistical analysis (min/max deviation)                      │
│ • Plot generation (not covered in this document)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
Input WAV File (stereo, up to 96 kHz)
         │
         ├──→ [get_audio] Read audio data
         │         │
         │         ├─→ If extract_sweeps == True:
         │         │      └──→ [slice_audio] Pilot tone detection
         │         │              ├─→ Hilbert envelope analysis
         │         │              ├─→ Find sweep start/end markers
         │         │              └─→ Extract L/R sweeps (duration varies by test record)
         │         │
         │         └─→ [ordersignal] Detect sweep direction
         │                ├─→ FFT of start chunk
         │                ├─→ FFT of end chunk
         │                └─→ Reverse if backward
         │
         ├──→ [Optional: riaaiir] RIAA filtering
         │         └─→ Bass, treble, or both, and inverse IIR
         │
         ├──→ [Optional: normxg7001] XG7001 correction
         |         └─→ via IIR
         │
         └──→ [createplotdata] FFT Analysis
                   │
                   ├──→ Band 1: 20-45 Hz @ 5 Hz resolution
                   │      ├─→ rfft: 19200-sample windows
                   │      ├─→ Peak detection per window
                   │      ├─→ Harmonic extraction
                   │      ├─→ bin_and_average: Averaging duplicates
                   │      └─→ Apply 26.03 dB offset
                   │
                   ├──→ Band 2: 50-90 Hz @ 10 Hz resolution
                   │      ├─→ rfft: 9600-sample windows
                   │      ├─→ Peak detection per window
                   │      ├─→ Harmonic extraction
                   │      ├─→ bin_and_average: Averaging duplicates
                   │      └─→ Apply 19.995 dB offset
                   │
                   ├──→ Band 3: 100-980 Hz @ 20 Hz resolution
                   │      ├─→ rfft: 4800-sample windows
                   │      ├─→ Peak detection per window
                   │      ├─→ Harmonic extraction
                   │      ├─→ bin_and_average: Averaging duplicates
                   │      └─→ Apply 13.99 dB offset
                   │
                   └──→ Band 4: 1000-50k Hz @ 100 Hz resolution
                          ├─→ rfft: 960-sample windows
                          ├─→ Peak detection per window
                          ├─→ Harmonic extraction
                          ├─→ bin_and_average: Averaging duplicates                             
                          └─→ No offset (reference band)
                                 │
                                 ↓
                       [Combine all bands]
                                 │
                                 ├──→ STR-100 correction (optional)
                                 ├──→ Low-pass smoothing (cutoff=0.5)
                                 ├──→ Normalize to 0 dB (default 1kHz)
                                 └──→ Slice to frequency range
                                          │
                                          ↓
                   Output: 8 arrays (freq + amp for fundamental, 
                                    stereo, 2nd/3rd harmonics)
                                          │
                                          └──→ [output_plot_data] CSV export
```

---

## Stage 1: Audio Input & Sweep Extraction

### `get_audio()` Function

**Location**: Lines 493-573  
**Purpose**: Unified audio input handling for both standalone (file) and web (upload) modes.

#### Function Signature
```python
def get_audio(input_data, environment='standalone', extract_sweeps=0, 
              test_record=None, save_sweeps=0, riaa_mode=0, 
              riaa_inverse=False, xg7001=False):
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_data` | str/bytes | Required | File path (standalone) or base64 audio data (web) |
| `environment` | str | 'standalone' | Execution context: 'standalone' or 'web' |
| `extract_sweeps` | int | 0 | Enable sweep extraction (0=off, 1=on) |
| `test_record` | str/None | None | Test record identifier (e.g., 'TRS1007', 'STR100') |
| `save_sweeps` | int | 0 | Save extracted sweeps to disk (0=off, 1=on) |
| `riaa_mode` | int | 0 | RIAA filter mode (0=off, 1=bass, 2=treble, 3=both) |
| `riaa_inverse` | bool | False | Apply inverse RIAA |
| `xg7001` | bool | False | Apply XG7001 test record correction |

#### Return Values

Returns tuple: `(signal_left, signal_right, Fs)`

| Return | Type | Description |
|--------|------|-------------|
| `signal_left` | ndarray | Left channel audio data (samples) |
| `signal_right` | ndarray | Right channel audio data (samples) |
| `Fs` | int | Sample rate in Hz |

#### Processing Flow

1. **Environment Detection**
   ```python
   if environment == 'web':
       # Decode base64 audio from web upload
       audio_bytes = base64.b64decode(input_data)
       Fs, audio = read(io.BytesIO(audio_bytes))
   else:
       # Read from file path
       Fs, audio = read(input_data)
   ```

2. **Audio Format Handling**
   - Normalizes data types (int16, int24, int32, float32)
   - Transposes to (channels, samples) format

3. **Sweep Extraction** (if `extract_sweeps=True`)
   - Calls `slice_audio()` (for supported test records)
   - Extracts separate left and right sweeps

4. **Pre-Processing Filters**
   - Optional RIAA filtering via `riaaiir()`
   - Optional XG7001 normalization via `normxg7001()`

5. **Sweep Orientation**
   - Calls `ordersignal()` to detect direction
   - Automatically reverses backward sweeps

#### Output
Returns tuple: `(signal_left, signal_right, Fs)`

---

### `slice_audio()` Function

**Location**: Lines 575-842  
**Purpose**: Extract left and right channel sweeps from test records using pilot tone detection.

#### Algorithm Overview

Supported test records that contain:
- 1 kHz pilot tone 
- Left channel sweep
- 1 kHz pilot tone 
- Right channel sweep

The function automatically detects these pilot tones to extract individual channel sweeps.

#### Function Signature

```python
def slice_audio(signal, Fs, test_record):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal` | ndarray | Stereo audio signal (channels, samples) |
| `Fs` | int | Sample rate in Hz |
| `test_record` | str | Test record identifier for pilot tone frequency selection |

#### Return Values

Returns tuple: `(left_sweep, right_sweep, Fs)`

| Return | Type | Description |
|--------|------|-------------|
| `left_sweep` | ndarray | Extracted left channel sweep (samples,) |
| `right_sweep` | ndarray | Extracted right channel sweep (samples,) |
| `Fs` | int | Sample rate in Hz |

#### Pilot Tone Detection Using Hilbert Transform

**Key Innovation**: Uses Hilbert envelope analysis instead of fragile peak-spacing algorithms.

```python
# 1. Bandpass filter around pilot tone frequency
sos = butter(4, [950/Fs_new, 1050/Fs_new], btype='band', output='sos')
filtered = sosfiltfilt(sos, audio_mono)

# 2. Hilbert transform to extract envelope
analytic_signal = hilbert(filtered)
envelope = np.abs(analytic_signal)

# 3. Smooth envelope with moving average
window_size = int(0.1 * Fs_new)  # 100ms window
envelope_smooth = uniform_filter1d(envelope, size=window_size)

# 4. Threshold detection
threshold = 0.3 * np.max(envelope_smooth)
pilot_active = envelope_smooth > threshold
```

**Why Hilbert Transform?**:
- **Robust**: Insensitive to exact pilot frequency (works across bandpass range)
- **Fast**: Single-pass envelope extraction
- **Reliable**: Not affected by noise or brief dropouts
- **Simple**: No complex peak-finding algorithms needed


#### Sweep Boundary Detection

```python
# Find rising edges (pilot tone starts)
pilot_diff = np.diff(pilot_active.astype(int))
pilot_starts = np.where(pilot_diff == 1)[0]

# Find falling edges (pilot tone ends)
pilot_ends = np.where(pilot_diff == -1)[0]
```


#### Output
Returns: `(left_sweep, right_sweep, Fs)`

---

## Stage 2: Sweep Detection & Orientation

### `ordersignal()` Function

**Location**: Lines 447-463  
**Purpose**: Detect if sweep runs low-to-high or high-to-low frequency and automatically correct orientation.

#### Function Signature

```python
def ordersignal(signal, Fs):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal` | ndarray | Input audio signal (channels, samples) or (samples,) |
| `Fs` | int | Sample rate in Hz |

#### Return Values

Returns tuple: `(oriented_signal, start_freq, end_freq)`

| Return | Type | Description |
|--------|------|-------------|
| `oriented_signal` | ndarray | Signal with correct time orientation (2D format) |
| `start_freq` | int | FFT bin index of dominant frequency at start |
| `end_freq` | int | FFT bin index of dominant frequency at end |

#### Algorithm

```python
def ordersignal(signal, Fs):
    F = int(Fs/100)  # 960 samples at 96 kHz
    win = ft_window(F)
    
    # Ensure 2D format
    if len(signal.shape) == 1:
        signal = np.expand_dims(signal, axis=0)
    
    # FFT of start chunk
    y_start = abs(np.fft.rfft(signal[0, 0:F] * win))
    minf = np.argmax(y_start)  # Dominant frequency at start
    
    # FFT of end chunk
    y_end = abs(np.fft.rfft(signal[0, -F:] * win))
    maxf = np.argmax(y_end)  # Dominant frequency at end
    
    # If end < start, sweep is backward
    if maxf < minf:
        maxf, minf = minf, maxf
        signal = np.flipud(signal)  # Reverse time axis
    
    return signal, minf, maxf
```

**Detection method**: Compare dominant frequencies at start vs. end
- Low→High: Normal forward sweep (no action)
- High→Low: Backward sweep (reverse signal)

---

## Stage 3: Pre-Processing Filters

### `riaaiir()` Function

**Location**: Lines 466-482  
**Purpose**: Apply RIAA equalization curves (standard phono pre-emphasis/de-emphasis).

#### Function Signature

```python
def riaaiir(sig, Fs, mode, inv):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `sig` | ndarray | Input audio signal |
| `Fs` | int | Sample rate in Hz (currently only 96000 supported) |
| `mode` | int | Filter mode: 0=none, 1=bass only, 2=treble only, 3=both |
| `inv` | int | Apply inverse filter (0=forward/pre-emphasis, 1=inverse/de-emphasis) |

#### Return Values

| Return | Type | Description |
|--------|------|-------------|
| `sig` | ndarray | Filtered audio signal |

#### RIAA Standard

The RIAA curve has three time constants:
- **Treble**: 75 µs (2122 Hz)
- **Bass**: 318 µs (500.5 Hz), 3180 µs (50.05 Hz)

Combined, this creates the standard phono equalization curve. These are implemented as Bass and Treble
with the abililty to inverse the equaliation to accomdate the various test record and recording chain
characteristics. 

#### Implementation

```python
def riaaiir(sig, Fs, mode, inv):
    if Fs == 96000:
        # Pre-computed IIR filter coefficients at 96 kHz
        at = [1, -0.66168391, -0.18158841]
        bt = [0.1254979638905360, 0.0458786797031512, 0.0018820452752401]
        ars = [1, -0.60450091, -0.39094593]
        brs = [0.90861261463964900, -0.52293147388301200, -0.34491369168550900]
    
    # Swap coefficients for inverse filtering
    if inv == 1:
        at, bt = bt, at
        ars, brs = brs, ars
    
    # Apply filters based on mode
    if mode == 1:  # Bass only
        sig = lfilter(brs, ars, sig)
    elif mode == 2:  # Treble only
        sig = lfilter(bt, at, sig)
    elif mode == 3:  # Both
        sig = lfilter(bt, at, sig)
        sig = lfilter(brs, ars, sig)
    
    return sig
```

#### Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| 0 | No filtering | Raw cartridge output analysis |
| 1 | Bass only | Isolate bass response |
| 2 | Treble only | Isolate treble response |
| 3 | Both (full RIAA) | Standard phono equalization |

#### Inverse Flag

- `inv=True`: Apply RIAA pre-emphasis (recording curve)
- `inv=False`: Apply RIAA de-emphasis (playback curve)


---

### `normxg7001()` Function

**Location**: Lines 485-490  
**Purpose**: Apply XG7001 test record specific correction.

#### Function Signature

```python
def normxg7001(signal, Fs):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal` | ndarray | Input audio signal |
| `Fs` | int | Sample rate in Hz (currently only 96000 supported) |

#### Return Values

| Return | Type | Description |
|--------|------|-------------|
| `signal` | ndarray | Corrected audio signal |

#### Implementation

```python
def normxg7001(signal, Fs):
    if Fs == 96000:
        b = [1.0080900, -0.9917285, 0]
        a = [1, -0.9998364, 0]
        signal = lfilter(b, a, signal)
    return signal
```

This is a simple IIR filter that corrects for XG7001 test record characteristics.

## Stage 4: FFT Analysis & Frequency Response Extraction

### `createplotdata()` Function

**Location**: Lines 296-444  
**Purpose**: Core analysis engine that transforms time-domain sweeps into frequency-domain response curves.

#### Function Signature

```python
def createplotdata(signal, Fs, iteration=[0], norm=[0], start_f=None, end_f=20000, 
                   str100=0, file0norm=0, normalize=1000):
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `signal` | ndarray | Required | Input audio signal (channels, samples) |
| `Fs` | int | Required | Sample rate in Hz (96000 or 192000) |
| `iteration` | list | [0] | Mutable list tracking iteration count |
| `norm` | list | [0] | Mutable list storing normalization reference |
| `start_f` | int/None | None | Start frequency for output range (Hz) |
| `end_f` | int | 20000 | End frequency for output range (Hz) |
| `str100` | int | 0 | Apply STR-100 correction (0=off, 1=on) |
| `file0norm` | int | 0 | Normalization mode (0=independent, 1=to first file) |
| `normalize` | int | 1000 | Reference frequency for 0 dB (Hz) |

#### Return Values

Returns 8 arrays as tuple:
```python
fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3
```

| Array | Description |
|-------|-------------|
| `fout` | Frequency array for primary channel (Hz) |
| `aout` | Amplitude array for primary channel (dB) |
| `foutx` | Frequency array for secondary channel (Hz) |
| `aoutx` | Amplitude array for secondary channel (dB) |
| `fout2` | Frequency array for 2nd harmonic (Hz) |
| `aout2` | Amplitude array for 2nd harmonic (dB) |
| `fout3` | Frequency array for 3rd harmonic (Hz) |
| `aout3` | Amplitude array for 3rd harmonic (dB) |

---

### Core Sub-Functions in `createplotdata`

#### 1. `bin_and_average()` Function

**Location**: Lines 298-312 (nested within `createplotdata`)  
**Purpose**: Average duplicate frequency measurements to reduce noise. Uses vectorized operations for performance.

#### Function Signature

```python
def bin_and_average(f, a, minf, maxf, fstep):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `f` | list/array | Frequency values from peak detection (Hz) - quantized to fstep multiples |
| `a` | list/array | Corresponding amplitudes (linear scale) |
| `minf` | float | Minimum frequency for output range (Hz) |
| `maxf` | float | Maximum frequency for output range (Hz) |
| `fstep` | float | Frequency step size (Hz) - defines FFT bin spacing |

#### Return Values

Returns tuple: `(f_out, a_out)`

| Return | Type | Description |
|--------|------|-------------|
| `f_out` | list | Unique frequency bins with measurements (Hz) |
| `a_out` | list | Averaged amplitudes (dB) for each bin |

##### Algorithm

```python
def bin_and_average(f, a, minf, maxf, fstep):
    # Ensure numpy arrays
    f, a = np.array(f), np.array(a)
    
    # Define bin edges
    bins = np.arange(minf, maxf + fstep, fstep)
    
    # Assign each frequency point to a bin (vectorized)
    indices = np.digitize(f, bins) - 1
    
    f_out, a_out = [], []
    
    # Process each bin
    for i, bin_center in enumerate(bins):
        mask = (indices == i)
        if np.any(mask):
            f_out.append(bin_center)
            # Average in linear scale, convert to dB
            a_out.append(20 * np.log10(np.mean(a[mask])))
    
    return f_out, a_out
```

##### Why Averaging is Needed

**Primary purpose: Noise reduction through averaging**

During log sweep FFT analysis, multiple consecutive windows peak at the same FFT bin:
- **Low frequencies** (~20-100 Hz): Around 12 measurements per bin
- **High frequencies** (~20 kHz): Typically 4-6 measurements per bin
- Averaging reduces noise by √N where N is the number of measurements

**Implementation: Vectorized binning**

Uses `np.digitize()` for performance - this vectorized approach groups all measurements by bin in one operation rather than looping through duplicates.

**Additional capability: Handles out-of-order data**

Occasionally at high frequencies, sweep speed variations cause measurements to arrive out of sequence (e.g., 20000, 20100, 20000, 20100, 20200 Hz). The binning approach groups by frequency regardless of arrival order, so this is handled correctly by design.

**Processing example**:
```
Input (may contain duplicates and occasional out-of-order):
  f = [20000, 20000, 20100, 20000, 20100, 20100, 20200, ...]
  a = [0.95, 0.96, 0.94, 0.97, 0.93, 0.95, 0.96, ...] (linear)

Grouping by bin (vectorized via np.digitize):
  Bin 20000: [0.95, 0.96, 0.97] → mean = 0.96 → -0.35 dB
  Bin 20100: [0.94, 0.93, 0.95] → mean = 0.94 → -0.52 dB
  Bin 20200: [0.96] → mean = 0.96 → -0.35 dB

Output:
  f_out = [20000, 20100, 20200, ...]
  a_out = [-0.35, -0.52, -0.35, ...] (dB)
```

**Benefits**:
- **Noise reduction**: Averaging 4-12 measurements significantly improves SNR
- **Proper dB conversion**: Averaging in linear domain before logarithmic conversion
- **Performance**: Vectorized operations using NumPy
- **Robustness**: Handles occasional out-of-order measurements by design

---

#### 2. `rfft()` Function

**Location**: Lines 315-351 (nested within `createplotdata`)  
**Purpose**: Core FFT analysis engine using **windowed, sliding analysis** of sweep signal.

#### Function Signature

```python
def rfft(signal, Fs, minf, maxf, fstep):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal` | ndarray | Input audio signal (channels, samples) or (samples,) |
| `Fs` | int | Sample rate in Hz |
| `minf` | float | Minimum frequency for this band (Hz) |
| `maxf` | float | Maximum frequency for this band (Hz) |
| `fstep` | float | Frequency resolution step (Hz) |

#### Return Values

Returns tuple: `(freq, amp, freqx, ampx, freq2h, amp2h, freq3h, amp3h)`

| Return | Type | Description |
|--------|------|-------------|
| `freq` | list | Fundamental frequencies for primary channel (Hz) |
| `amp` | list | Fundamental amplitudes for primary channel (linear) |
| `freqx` | list | Fundamental frequencies for secondary channel (Hz) |
| `ampx` | list | Fundamental amplitudes for secondary channel (linear) |
| `freq2h` | list | Fundamental frequencies where 2nd harmonic detected (Hz) |
| `amp2h` | list | 2nd harmonic amplitudes (linear) |
| `freq3h` | list | Fundamental frequencies where 3rd harmonic detected (Hz) |
| `amp3h` | list | 3rd harmonic amplitudes (linear) |

##### Critical Concept: Slicing vs. Full-Signal FFT

**The Key Innovation**: This function analyzes the sweep signal in **time slices** rather than performing a single FFT on the entire signal.

**Why This Matters**:

A log sweep contains **all frequencies over time**, not simultaneously:
- At t=0s: 20 Hz
- At t=16.7s: 200 Hz (1 decade)
- At t=33.3s: 2 kHz (2 decades)
- At t=50s: 20 kHz (3 decades)

**If you ran a full-signal FFT** (traditional approach):
- All frequencies would appear in the spectrum
- Amplitude would be related to time spent at each frequency
- Log sweep = more time at low frequencies → 10 dB/decade slope artifact
- **Result**: Meaningless frequency response that reflects sweep characteristics, not cartridge response

**The slicing approach** (what this function does):
- Divide signal into short time windows (10-200 ms)
- Each window captures approximately **one frequency**
- FFT of each window reveals the **instantaneous frequency** and **its amplitude**
- **Result**: True frequency response independent of sweep speed or type

This is what makes SJPlot's analysis **agnostic to sweep characteristics**:
- Works with any sweep speed
- Works with linear or logarithmic sweeps
- Amplitude accuracy is independent of time-per-frequency

##### Function Signature

```python
def rfft(signal, Fs, minf, maxf, fstep):
```

##### Algorithm Breakdown

**1. Window Size Calculation**
```python
F = int(Fs/fstep)  # Window size in samples
win = ft_window(F)  # Flat-top window for amplitude accuracy
```

The window size is **inversely proportional to frequency resolution**:
- `fstep = 5 Hz → F = 19,200 samples (200 ms @ 96 kHz)`
- `fstep = 100 Hz → F = 960 samples (10 ms @ 96 kHz)`

**Why variable window sizes?**:
- **Bass frequencies** need long windows for frequency resolution
- **Treble frequencies** can use short windows (faster analysis)
- Each band gets optimal time/frequency tradeoff

**2. Signal Format Handling**
```python
if len(signal.shape) == 1:  # mono signal
    signal = np.expand_dims(signal, axis=0)
```

Ensures uniform 2D processing: (channels, samples)

**3. Sliding Window Analysis**
```python
for x in range(0, signal.shape[1] - F, F):
```

**Critical**: Non-overlapping windows, stride = F
- Each window is **independent** and contiguous
- No overlap = faster processing
- Sufficient for slow-changing sweep signals

**4. FFT and Peak Detection**
```python
y0 = abs(np.fft.rfft(signal[0, x:x + F] * win))
f0 = np.argmax(y0)  # Find dominant frequency
```

**Process per window**:
1. Extract F samples
2. Apply flat-top window (amplitude accuracy)
3. Compute FFT
4. Find bin with maximum amplitude = sweep frequency at this time

**Why peak detection works**:
- Sweep signal is **one dominant frequency** per time window
- Peak is typically 40-60 dB above noise floor
- Harmonics are much lower amplitude (handled separately)

**5. Fundamental Frequency Extraction**
```python
if f0 >= minf/fstep and f0 <= maxf/fstep:
    freq.append(f0*fstep)  # Bin number → Hz
    amp.append(y0[f0])     # FFT magnitude (linear)
```

**Frequency bounds checking**:
- Only stores data within expected frequency band
- Prevents contamination from out-of-band content
- `f0` is bin index, multiply by `fstep` to get Hz

**6. Second Harmonic Detection**
```python
if 2*f0 < F/2-2 and f0 > minf/fstep and f0 < maxf/fstep:
    f2 = np.argmax(y0[(2*f0)-2:(2*f0)+2])  # Search ±2 bins
    freq2h.append(f0*fstep)  # Store fundamental frequency
    amp2h.append(y0[2*f0-2+f2])  # Store 2nd harmonic amplitude
```

**Key points**:
- **Nyquist check**: `2*f0 < F/2-2` ensures 2nd harmonic is within spectrum
- **Search window**: ±2 bins accounts for frequency estimation error
- **Storage**: Records fundamental frequency, not 2×f (for alignment)

**Why ±2 bins?**:
- Peak detection accuracy is ±1 bin
- Harmonic may be slightly off from exact 2× due to:
  - FFT bin spacing
  - Slight frequency modulation in sweep
  - Cartridge non-linearity

**7. Third Harmonic Detection**
```python
if 3*f0 < F/2-2 and f0 > minf/fstep and f0 < maxf/fstep:
    f3 = np.argmax(y0[(3*f0)-2:(3*f0)+2])
    freq3h.append(f0*fstep)
    amp3h.append(y0[3*f0-2+f3])
```

Identical logic to 2nd harmonic, searches around `3*f0`.

**8. Stereo Channel Processing**
```python
if signal.shape[0] > 1:  # Process second channel if stereo
    y1 = abs(np.fft.rfft(signal[1, x:x + F] * win))
    f1 = np.argmax(y1)
    if f0 >= minf/fstep and f0 <= maxf/fstep:  # Use primary channel range
        freqx.append(f1*fstep)
        ampx.append(y1[f1])
```

**Important**: Uses `f0` (primary channel) for frequency range check
- Ensures frequency alignment between channels
- Allows direct L/R comparison
- Crosstalk analysis requires aligned frequencies

##### Return Values
```python
return freq, amp, freqx, ampx, freq2h, amp2h, freq3h, amp3h
```

All values in **linear scale** (not dB), with **duplicate measurements** per bin (bin_and_average will consolidate).

---

#### 3. `normstr100()` Function

**Location**: Lines 354-360 (nested within `createplotdata`)  
**Purpose**: Compensate for STR-100 test record's non-standard bass curve.

#### Function Signature

```python
def normstr100(f, a):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `f` | list | Frequency array (Hz) |
| `a` | list | Amplitude array (dB) |

#### Return Values

| Return | Type | Description |
|--------|------|-------------|
| `a` | list | Corrected amplitude array with bass boost applied (dB) |

##### Background

The STR-100 test record was manufactured with a **-6.02 dB/octave rolloff** from 500 Hz down to 40 Hz (the cutting characteristic used during record production). To measure cartridge response accurately, this intentional rolloff must be compensated.

##### Implementation

```python
def normstr100(f, a):
    fmin = 40
    fmax = 500
    slope = -6.02  # dB/octave
    
    for x in range(find_nearest(f, fmin), find_nearest(f, fmax)):
        a[x] = a[x] + 20*np.log10(1*((f[x])/fmax)**((slope/20)/np.log10(2)))
    
    return a
```

##### Mathematics

The correction formula creates a **+6.02 dB/octave boost** below 500 Hz:

```
correction(f) = 20*log10((f/500)^(-6.02/20/log10(2)))
              = 20*log10((f/500)^(-1.0))
```

**Examples**:
- At 500 Hz: `20*log10(500/500)^(-1) = 0.00 dB` (no correction)
- At 250 Hz: `20*log10(250/500)^(-1) = +6.02 dB` (1 octave down)
- At 125 Hz: `20*log10(125/500)^(-1) = +12.04 dB` (2 octaves down)

This exactly cancels the test record's rolloff, revealing true cartridge response.

---

#### 4. `process_chunk()` Function

**Location**: Lines 363-375 (nested within `createplotdata`)  
**Purpose**: Orchestrate the complete processing pipeline for one frequency band.

#### Function Signature

```python
def process_chunk(signal, Fs, fmin, fmax, step, offset):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal` | ndarray | Input audio signal (channels, samples) |
| `Fs` | int | Sample rate in Hz |
| `fmin` | float | Minimum frequency for this band (Hz) |
| `fmax` | float | Maximum frequency for this band (Hz) |
| `step` | float | Frequency resolution step (Hz) |
| `offset` | float | FFT window size compensation offset (dB) |

#### Return Values

Returns tuple: `(f, a, fx, ax, f2, a2, f3, a3)`

| Return | Type | Description |
|--------|------|-------------|
| `f` | list | Regularized frequency array for primary channel (Hz) |
| `a` | list | Compensated amplitude array for primary channel (dB) |
| `fx` | list | Regularized frequency array for secondary channel (Hz) |
| `ax` | list | Compensated amplitude array for secondary channel (dB) |
| `f2` | list | Frequency array for 2nd harmonic (Hz) |
| `a2` | list | Compensated 2nd harmonic amplitude array (dB) |
| `f3` | list | Frequency array for 3rd harmonic (Hz) |
| `a3` | list | Compensated 3rd harmonic amplitude array (dB) |

##### Implementation

```python
def process_chunk(signal, Fs, fmin, fmax, step, offset):
    # 1. FFT analysis
    f, a, fx, ax, f2, a2, f3, a3 = rfft(signal, Fs, fmin, fmax, step)
    
    # 2. Regularize frequency spacing
    f, a = bin_and_average(f, a, fmin, fmax, step)
    fx, ax = bin_and_average(fx, ax, fmin, fmax, step)
    f2, a2 = bin_and_average(f2, a2, fmin, fmax, step)
    f3, a3 = bin_and_average(f3, a3, fmin, fmax, step)
    
    # 3. Apply FFT window size compensation
    a = [amp - offset for amp in a]
    ax = [amp - offset for amp in ax] if ax else []
    a2 = [amp - offset for amp in a2]
    a3 = [amp - offset for amp in a3]
    
    return f, a, fx, ax, f2, a2, f3, a3
```

##### FFT Window Size Compensation (Offset Parameter)

The `offset` parameter compensates for **FFT magnitude scaling** differences between bands.

**The Problem**: FFT magnitude is proportional to window size
```
FFT_magnitude = signal_amplitude × N / 2
```

Where N = window size in samples.

**Example**:
- Band 1: N = 19,200 samples
- Band 4: N = 960 samples
- Ratio: 19,200 / 960 = 20
- dB difference: 20*log10(20) = **26.02 dB**

**Without compensation**: There would be 26 dB jumps at band boundaries!

**With compensation**: Offsets normalize all bands to Band 4 (reference)

| Band | Window Size | Theoretical Offset | Empirical Offset | Difference |
|------|-------------|-------------------|------------------|------------|
| 1 (5 Hz) | 19,200 | 26.021 dB | 26.03 dB | +0.009 dB |
| 2 (10 Hz) | 9,600 | 20.000 dB | 19.995 dB | -0.005 dB |
| 3 (20 Hz) | 4,800 | 13.979 dB | 13.99 dB | +0.011 dB |
| 4 (100 Hz) | 960 | 0.000 dB | 0.00 dB | 0.000 dB |

**Empirical values** (used in code) were determined by running a flat synthetic sweep and measuring required offsets for seamless band transitions. They differ slightly from theoretical due to flat-top window coherent gain variations.

---

#### 5. `slice_frequency_range()` Function

**Location**: Lines 380-397 (nested within `createplotdata`)  
**Purpose**: Filter output to user-specified frequency range.

#### Function Signature

```python
def slice_frequency_range(freq_array, amp_array, start_f=None, end_f=None):
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `freq_array` | list | Required | Frequency array (Hz) |
| `amp_array` | list | Required | Amplitude array (dB) |
| `start_f` | float/None | None | Start frequency for output (Hz), None = no limit |
| `end_f` | float/None | None | End frequency for output (Hz), None = no limit |

#### Return Values

Returns tuple: `(freq_array, amp_array)`

| Return | Type | Description |
|--------|------|-------------|
| `freq_array` | list | Sliced frequency array within specified range |
| `amp_array` | list | Sliced amplitude array within specified range |

##### Implementation

```python
def slice_frequency_range(freq_array, amp_array, start_f=None, end_f=None):
    # Handle start
    if not start_f:  # Catches None, "", 0
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
```

**Flexible handling**:
- `None`, `""`, `0` all treated as "no limit"
- Binary search via `find_nearest()` for efficiency
- Bounds checking prevents errors
- Inclusive slicing (`idx_max+1`)

---

### Multi-Band Processing

#### Band Configuration

```python
for fmin, fmax, step, offset in [(20,45,5,26.03), (50,90,10,19.995), 
                                  (100,980,20,13.99), (1000,50000,100,0)]:
    f, a, fx, ax, f2, a2, f3, a3 = process_chunk(signal, Fs, fmin, fmax, step, offset)
    fout.extend(f); aout.extend(a); foutx.extend(fx); aoutx.extend(ax)
    fout2.extend(f2); aout2.extend(a2); fout3.extend(f3); aout3.extend(a3)
```

| Band | Frequency Range | Step | Window Size (96kHz) | Window Duration | Points | Rationale |
|------|----------------|------|---------------------|-----------------|--------|-----------|
| 1 | 20-45 Hz | 5 Hz | 19,200 samples | 200 ms | 6 | Bass needs high resolution, long window for frequency accuracy |
| 2 | 50-90 Hz | 10 Hz | 9,600 samples | 100 ms | 5 | Bass transition region |
| 3 | 100-980 Hz | 20 Hz | 4,800 samples | 50 ms | 45 | Midrange, balanced resolution |
| 4 | 1000-50000 Hz | 100 Hz | 960 samples | 10 ms | 491 | Treble, lower resolution sufficient, faster processing |

**Total**: ~547 frequency measurements across 4.5 decades

#### Why Multi-Resolution?

**Single resolution approach problems**:
1. **High resolution everywhere** (5 Hz):
   - 10,000 frequency points (20-50 kHz @ 5 Hz)
   - Processing time: ~20× slower
   - Unnecessary treble detail
   - Excessive data for plotting

2. **Low resolution everywhere** (100 Hz):
   - Only ~200 frequency points
   - Insufficient bass detail (critical range)
   - Poor frequency resolution

**Multi-resolution benefits**:
- **Optimal resolution per range**: Detail where it matters (bass)
- **Fast processing**: Shorter windows for treble
- **Efficient data**: ~500 points is ideal for plotting
- **Better time/frequency tradeoff**: Each band optimized

---

### Low-Pass Smoothing Filter

```python
sos = iirfilter(3, 0.5, btype='lowpass', output='sos')
aout = sosfiltfilt(sos, aout)
aout2 = sosfiltfilt(sos, aout2)
aout3 = sosfiltfilt(sos, aout3)
if len(aoutx) > 0:
    aoutx = sosfiltfilt(sos, aoutx)
```

#### Purpose

**Not** a signal filter - this is a **data smoothing filter** applied to the frequency response curve itself.

**What it does**:
- Removes high-frequency noise in the frequency response plot
- Smooths out small bumps from measurement noise
- Improves visual appearance
- Zero-phase filtering preserves peak locations

#### Filter Design

- **Type**: 3rd-order Butterworth low-pass
- **Cutoff**: 0.5 (normalized frequency)
- **Implementation**: SOS (second-order sections) for numerical stability
- **Method**: `sosfiltfilt` = zero-phase forward-backward filtering

#### Interpretation

The "cutoff" of 0.5 is relative to the **Nyquist frequency of the data points**, not the audio signal.

For frequency response data with mixed spacing (5, 10, 20, 100 Hz), this creates **smooth curves** without losing real features.

**Effect on output**:
- Raw data: ±0.5 dB noise
- After smoothing: ±0.1 dB smooth curve
- Narrow resonances preserved
- Broad trends enhanced

---

### Normalization

#### Calculation

```python
if file0norm == 0 and iteration[0] == 0:
    i = find_nearest(fout, normalize)  # Default: 1000 Hz
    norm[0] = aout[i]
elif file0norm == 1:
    i = find_nearest(fout, normalize)
    norm[0] = aout[i]
```

#### Application

```python
aout = [a - norm[0] for a in aout]
aoutx = [a - norm[0] for a in aoutx] if len(aoutx) > 0 else []
aout2 = [a - norm[0] for a in aout2]
aout3 = [a - norm[0] for a in aout3]
```

#### Modes

**Mode 0** (`file0norm=0`): **Independent normalization**
- Each file normalized to its own 1 kHz point
- Reveals relative frequency response shape
- First iteration only (subsequent calls use same reference)

**Mode 1** (`file0norm=1`): **Comparative normalization**
- All files normalized to first file's 1 kHz
- Allows direct amplitude comparison between measurements
- Shows absolute level differences


---

### Helper Functions

#### `ft_window()` Function

**Location**: Lines 270-275  
**Purpose**: Generate flat-top window for FFT analysis.

#### Function Signature

```python
def ft_window(n):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `n` | int | Window length in samples |

#### Return Values

| Return | Type | Description |
|--------|------|-------------|
| `w` | ndarray | Flat-top window coefficients, length n |

#### Implementation

```python
def ft_window(n):
    a0, a1, a2, a3, a4 = 0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368
    x = np.arange(n)
    w = (a0 - a1*np.cos(2*np.pi*x/(n-1)) + a2*np.cos(4*np.pi*x/(n-1)) - 
         a3*np.cos(6*np.pi*x/(n-1)) + a4*np.cos(8*np.pi*x/(n-1)))
    return w
```

**Window type**: 5-term flat-top (SRS flat-top)

**Characteristics**:
- **Amplitude accuracy**: ±0.01 dB (excellent for measurements)
- **Scalloping loss**: <0.01 dB
- **Frequency resolution**: Poor (wide main lobe)

**Why flat-top for this application?**

| Window | Amplitude Accuracy | Frequency Resolution | Best Use |
|--------|-------------------|---------------------|----------|
| Rectangular | ±3.9 dB | Excellent | Transient analysis |
| Hann | ±1.4 dB | Good | General FFT |
| Flat-top | ±0.01 dB | Poor | **Amplitude measurements** |

For phono cartridge frequency response, **amplitude accuracy is critical**. We're measuring "how loud is 1 kHz?" not "is it exactly 1000.0 Hz?". Flat-top is the correct choice.

---

#### `find_nearest()` Function

**Location**: Lines 278-292  
**Purpose**: Efficiently find closest value index in sorted array.

#### Function Signature

```python
def find_nearest(array, value):
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `array` | array-like | Sorted array to search |
| `value` | float | Target value to find |

#### Return Values

| Return | Type | Description |
|--------|------|-------------|
| `idx` | int | Index of closest value in array |

#### Implementation

```python
def find_nearest(array, value):
    idx = np.searchsorted(array, value)  # Binary search O(log n)
    
    # Edge cases
    if idx == 0:
        return 0
    if idx == len(array):
        return len(array) - 1
    
    # Choose closer of idx or idx-1
    if abs(array[idx] - value) < abs(array[idx-1] - value):
        return idx
    else:
        return idx - 1
```

**Why binary search?**: O(log n) vs O(n) for linear search. For 500-point array: 9 comparisons vs 250 average.

---

## Stage 5: Post-Processing & Output

### `output_plot_data()` Function

**Location**: Lines 897-952  
**Purpose**: Generate CSV export of frequency response data for external analysis.

#### What is `plot_data_out`?

When the user enables `plot_data_out=True`, SJPlot generates a CSV file containing the **processed frequency response data** that would be plotted. This allows:
- Import into Excel or other analysis tools
- Custom plotting with matplotlib/gnuplot
- Statistical analysis
- Long-term data archival
- Comparison with measurements from other tools

#### Data Pipeline Location

The CSV data comes from the **output of `createplotdata()`** after all processing is complete:

```
createplotdata output
        ↓
(fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3)
        ↓
output_plot_data()
        ↓
CSV file
```

#### CSV Format

```python
def _generate_csv_string(fo, ao, aox, ao2h, ao3h):
    """Generate CSV string from plot data arrays."""
    csv_lines = ["Frequency (Hz),Amplitude (dB),Stereo (dB),2nd Harmonic (dB),3rd Harmonic (dB)"]
    
    for i in range(len(fo)):
        line = f"{fo[i]:.2f},{ao[i]:.4f}"
        
        # Add stereo channel if present
        if aox and i < len(aox):
            line += f",{aox[i]:.4f}"
        else:
            line += ","
        
        # Add 2nd harmonic if present
        if ao2h and i < len(ao2h):
            line += f",{ao2h[i]:.4f}"
        else:
            line += ","
        
        # Add 3rd harmonic if present
        if ao3h and i < len(ao3h):
            line += f",{ao3h[i]:.4f}"
        else:
            line += ","
        
        csv_lines.append(line)
    
    return "\n".join(csv_lines)
```

#### Example CSV Output

```csv
Frequency (Hz),Amplitude (dB),Stereo (dB),2nd Harmonic (dB),3rd Harmonic (dB)
20.00,-1.2300,-1.2500,-65.4300,-72.1200
25.00,-1.1800,-1.2100,-64.8900,-71.5600
30.00,-1.1200,-1.1500,-64.2100,-70.8900
...
1000.00,0.0000,-0.0200,-58.2300,-68.4500
...
20000.00,-2.3400,-2.4100,-52.1200,-61.8900
```

#### Column Descriptions

| Column | Description | Units | Source |
|--------|-------------|-------|--------|
| Frequency | Frequency point | Hz | `fout` |
| Amplitude | Primary channel response | dB | `aout` (normalized to 1 kHz = 0 dB) |
| Stereo | Secondary channel response | dB | `aoutx` |
| 2nd Harmonic | Second harmonic distortion | dB | `aout2` |
| 3rd Harmonic | Third harmonic distortion | dB | `aout3` |

**Missing data**: Represented by empty fields (stereo/harmonics may not extend to all frequencies)

#### File Naming

```python
if file1_data:
    filename = f"{PLOT_INFO}_comparison_{timestamp}.csv"
else:
    filename = f"{PLOT_INFO}_{timestamp}.csv"
```

Where `PLOT_INFO` is user-provided metadata (e.g., "AT-VM95ML_47k_TRS1007").

#### Web vs Standalone

**Web mode**: CSV data sent to browser for download  
**Standalone mode**: CSV file saved to disk alongside plot image

---

### Crosstalk Calculation

Crosstalk is measured at 1 kHz by analyzing opposite-channel signal strength.

```python
# Extract 1 kHz amplitude from opposite channel
idx_1k = find_nearest(fo0, 1000)
left_crosstalk = aox0[idx_1k]  # Right channel signal when left plays
right_crosstalk = (if file1_data) ao1[idx_1k]  # Right channel measurement

logger.info(f"Left crosstalk @1kHz: {left_crosstalk:.2f}dB")
logger.info(f"Right crosstalk @1kHz: {right_crosstalk:.2f}dB")
```

**Typical values**:
- Excellent: < -30 dB
- Good: -25 to -30 dB
- Acceptable: -20 to -25 dB
- Poor: > -20 dB

---

## Known Issues and Limitations

### Smoothing Filter Artifact with Non-Uniform Data Spacing

#### Problem Description

The low-pass smoothing filter uses `sosfiltfilt()`, which **assumes uniform sample spacing**. However, `createplotdata` produces data with **four different frequency spacings**:

- Band 1: 5 Hz spacing
- Band 2: 10 Hz spacing  
- Band 3: 20 Hz spacing
- Band 4: 100 Hz spacing

When aggressive smoothing is used (e.g., cutoff = 0.02 instead of default 0.5), this creates **visible "kinks" at band boundaries**. The kink is not an amplitude discontinuity but a **discontinuity in the first derivative** (slope).

#### Example Measurements

At the 980→1000 Hz boundary with cutoff = 0.02:

| Frequency | Amplitude | Slope (dB/Hz) | Notes |
|-----------|-----------|---------------|-------|
| 980 Hz | +0.0000628 dB | **-0.00000314** | End of Band 3 (20 Hz spacing) |
| 1000 Hz | +0.0000000 dB | **-0.00000068** | Start of Band 4 (100 Hz spacing) |

The slope changes by **~78%** at the boundary, creating a visible corner in the curve.

#### Root Cause

The `sosfiltfilt()` function interprets each data point as having fixed spacing. When spacing changes from 20 Hz to 100 Hz, the filter's effective cutoff (relative to data "Nyquist") changes 5×, creating different filtering strength on each side of the boundary.

#### Suggested Solutions

**Option 1: Resample to Uniform Spacing** (Recommended)

```python
from scipy.interpolate import interp1d

# Before smoothing
fout_uniform = np.arange(20, 20000, 5)  # 5 Hz uniform
interpolator = interp1d(fout, aout, kind='cubic')
aout_uniform = interpolator(fout_uniform)

# Apply smoothing to uniform data
sos = iirfilter(3, 0.5, btype='lowpass', output='sos')
aout_smoothed = sosfiltfilt(sos, aout_uniform)

# Interpolate back to original points
aout_final = interp1d(fout_uniform, aout_smoothed, kind='cubic')(fout)
```

**Pros**: Eliminates kink completely  
**Cons**: Additional computation, slight interpolation artifacts

**Option 2: Limit Smoothing Aggressiveness**

```python
# Stay above cutoff 0.3 to minimize artifacts
sos = iirfilter(3, 0.5, btype='lowpass', output='sos')
```

**Pros**: Simple, no code changes  
**Cons**: Cannot use aggressive smoothing when desired

**Recommendation**: For standard analysis (cutoff ≥ 0.5), current approach works well. For aggressive smoothing applications, implement Option 1.

---

## Performance Analysis

### Current Performance Profile

**Test case**: 50-second stereo sweep, 96 kHz (typical test record recording), apply RIAA base emphasis  
**Total runtime**: 1.96 seconds

#### Time Breakdown

| Stage | Time | Percentage | Description |
|-------|------|------------|-------------|
| File I/O | 0.16s | 8% | WAV file reading |
| Sweep extraction | 0.43s | 22% | Pilot tone detection via Hilbert |
| Initial processing | 0.18s | 9% | Cropping, validation |
| createplotdata (L) | 0.27s | 14% | Left channel FFT analysis |
| createplotdata (R) | 0.26s | 13% | Right channel FFT analysis |
| Matplotlib rendering | 0.66s | 34% | Plot generation and save |
| **Total** | **1.96s** | **100%** | |

#### Historical Performance

| Version | Total Time | Key Optimizations |
|---------|-----------|------------------|
| 18.3.8 (old) | 6.94s | Baseline |
| 18.6.4 (current) | 1.96s | Hilbert envelope (7.7× faster sweep extraction), Vectorized FFT (5× faster analysis) |
| **Improvement** | **-4.98s** | **72% faster (3.5× speedup)** |

The major optimization was replacing peak-spacing pilot tone detection with **Hilbert envelope analysis**, achieving **40× speedup** in sweep extraction (3.3s → 0.43s).

### Attempted Optimizations (Unsuccessful)

During development, several optimizations were tested but provided no benefit or degraded performance:

#### 1. `scipy.stats.binned_statistic` for Binning

**Theory**: Vectorized C implementation should be faster than Python loops.

**Test result**: **3% slower** in real-world usage
- Overhead of function call and setup exceeded benefit
- Original loop-based approach is already quite fast for ~1000 points
- **Status**: Not implemented

#### 2. Window Function Caching

**Theory**: Cache pre-computed windows to avoid repeated calculation.

**Test result**: **No measurable impact**
- Windows are computed 4 times per analysis (once per band)
- Computation time: <1ms per window
- Total savings: ~3ms (0.15% of runtime)
- **Status**: Not implemented (negligible benefit)

#### 3. Parallel Band Processing

**Theory**: Process 4 frequency bands in parallel using threading/multiprocessing.

**Test result**: **~30% slower** due to overhead
- Python's GIL prevents true parallelism for CPU-bound tasks
- Thread creation overhead: ~100ms
- Per-band processing: ~30ms
- Overhead >> benefit
- **Status**: Not implemented (counterproductive)

### Bottleneck Analysis

Current runtime is dominated by:

1. **Matplotlib (34%)**: Inherently slow, difficult to optimize without changing libraries
2. **FFT analysis (27%)**: Already well-optimized, near theoretical minimum
3. **Sweep extraction (22%)**: Already 40× faster than original, further optimization unlikely

**Conclusion**: 1.96s runtime is excellent for this type of analysis. Further optimization would require:
- Switching to faster plotting library (plotly, bokeh)
- Implementing Cython/C extensions for FFT loops
- Batch processing multiple files in parallel

For single-file analysis, current performance is more than adequate.

---

## Summary

The SJPlot signal processing pipeline transforms phono cartridge test recordings into frequency response data through five sophisticated stages:

1. **Audio Input & Sweep Extraction**: Robust Hilbert envelope-based pilot tone detection (40× faster than previous method)
2. **Sweep Orientation**: Automatic detection and correction of backward sweeps
3. **Pre-Processing Filters**: Optional RIAA and test record-specific corrections
4. **FFT Analysis**: Multi-resolution windowed analysis with 4 frequency bands optimized for resolution vs. speed
5. **Post-Processing**: Smoothing, normalization, and CSV export

**Key Technical Innovations**:
- **Slicing-based FFT analysis**: Processes sweep in time windows, making analysis agnostic to sweep speed and type (avoids 10 dB/decade artifact from full-signal FFT)
- **Multi-resolution bands**: Optimal frequency resolution per range (5-100 Hz steps)
- **FFT window size compensation**: Seamless stitching of bands with different window sizes
- **Flat-top windowing**: ±0.01 dB amplitude accuracy for precision measurements
- **Hilbert envelope detection**: Robust pilot tone detection for sweep extraction


**Output Quality**: Suitable for professional phono cartridge analysis with harmonic distortion measurement, stereo channel comparison, and crosstalk analysis.

This is production-quality audio analysis code implementing best practices for frequency response measurement of audio transducers.
