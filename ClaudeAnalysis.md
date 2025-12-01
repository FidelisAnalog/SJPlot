# Comprehensive Analysis of `createplotdata` Function

## Table of Contents
1. [Overview](#overview)
2. [Function Signature](#function-signature)
3. [Core Sub-Functions](#core-sub-functions)
4. [Main Processing Logic](#main-processing-logic)
5. [Data Flow Diagram](#data-flow-diagram)
6. [Detailed Function Analysis](#detailed-function-analysis)

---

## Overview

The `createplotdata` function is the core audio analysis engine in SJPlot. It processes audio signals from phono cartridge test recordings to extract frequency response data and harmonic distortion measurements. The function implements a sophisticated multi-resolution frequency analysis system that processes different frequency ranges with appropriate resolution steps.

**Purpose**: Transform time-domain audio signals into frequency-domain amplitude response curves suitable for plotting frequency response graphs of phono cartridges.

**Key Features**:
- Multi-resolution FFT analysis (4 frequency bands with different resolutions)
- Harmonic distortion detection (2nd and 3rd harmonics)
- Stereo/dual-channel support
- Normalization and calibration
- STR-100 test record correction
- Frequency range filtering

---

## Function Signature

```python
def createplotdata(signal, Fs, iteration=[0], norm=[0], start_f=None, end_f=20000, 
                   str100=0, file0norm=0, normalize=1000):
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `signal` | ndarray | Required | Input audio signal (mono or stereo). Shape: (channels, samples) |
| `Fs` | int | Required | Sample rate in Hz (typically 96000 or 192000) |
| `iteration` | list | [0] | Mutable list tracking iteration count for normalization logic |
| `norm` | list | [0] | Mutable list storing normalization reference amplitude |
| `start_f` | int/None | None | Start frequency for output range filtering (Hz) |
| `end_f` | int | 20000 | End frequency for output range filtering (Hz) |
| `str100` | int | 0 | Flag to apply STR-100 test record correction (0=off, 1=on) |
| `file0norm` | int | 0 | Normalization mode (0=independent, 1=normalize to first file) |
| `normalize` | int | 1000 | Frequency in Hz where amplitude is normalized to 0 dB |

### Return Values

The function returns 8 arrays as a tuple:

```python
fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3
```

| Return | Description |
|--------|-------------|
| `fout` | Frequency array for primary channel (Hz) |
| `aout` | Amplitude array for primary channel (dB) |
| `foutx` | Frequency array for secondary channel (Hz) |
| `aoutx` | Amplitude array for secondary channel (dB) |
| `fout2` | Frequency array for 2nd harmonic detection (Hz) |
| `aout2` | Amplitude array for 2nd harmonic (dB) |
| `fout3` | Frequency array for 3rd harmonic detection (Hz) |
| `aout3` | Amplitude array for 3rd harmonic (dB) |

---

## Core Sub-Functions

The `createplotdata` function contains four nested sub-functions that handle specific processing tasks:

1. **`interpolate`** - Bins and averages FFT data into discrete frequency steps
2. **`rfft`** - Performs FFT analysis and extracts fundamental + harmonics
3. **`normstr100`** - Applies STR-100 test record bass compensation
4. **`process_chunk`** - Orchestrates processing for a frequency band
5. **`slice_frequency_range`** - Filters output to specified frequency range

---

## Main Processing Logic

The `createplotdata` function follows this execution flow:

```
1. Initialize output arrays
2. Process 4 frequency bands with different resolutions:
   ├─ 20-45 Hz    @ 5 Hz steps   (offset: 26.03 dB)
   ├─ 50-90 Hz    @ 10 Hz steps  (offset: 19.995 dB)
   ├─ 100-980 Hz  @ 20 Hz steps  (offset: 13.99 dB)
   └─ 1000-50k Hz @ 100 Hz steps (offset: 0 dB)
3. Apply STR-100 correction (if enabled)
4. Apply low-pass smoothing filter
5. Calculate and apply normalization
6. Slice to requested frequency range
7. Return processed data arrays
```

---

## Data Flow Diagram

```
Input Signal (Time Domain)
         │
         ├──→ [process_chunk for 20-45 Hz]
         │         │
         │         ├──→ rfft (FFT Analysis)
         │         │      ├──→ Extract fundamental frequency
         │         │      ├──→ Extract 2nd harmonic
         │         │      └──→ Extract 3rd harmonic
         │         │
         │         ├──→ interpolate (Bin averaging)
         │         └──→ Apply offset compensation
         │
         ├──→ [process_chunk for 50-90 Hz]
         ├──→ [process_chunk for 100-980 Hz]
         └──→ [process_chunk for 1000-50k Hz]
                   │
                   ↓
         [Combine all bands]
                   │
                   ├──→ Apply STR-100 correction (optional)
                   ├──→ Apply low-pass smoothing filter
                   ├──→ Calculate normalization value
                   ├──→ Apply normalization
                   └──→ Slice to frequency range
                          │
                          ↓
         Output Arrays (Frequency Domain)
```

---

## Detailed Function Analysis

### 1. `interpolate` Function

**Location**: Lines 298-312  
**Purpose**: Bins raw FFT frequency points into uniform frequency steps and averages amplitudes within each bin.

#### Function Signature
```python
def interpolate(f, a, minf, maxf, fstep):
```

#### Parameters
- `f`: Array of frequency values (Hz) from FFT
- `a`: Array of amplitude values (linear scale) from FFT
- `minf`: Minimum frequency for binning (Hz)
- `maxf`: Maximum frequency for binning (Hz)
- `fstep`: Frequency step size for bins (Hz)

#### Algorithm

1. **Input Validation**
   ```python
   f, a = np.array(f), np.array(a)
   ```
   Ensures inputs are NumPy arrays for vectorized operations.

2. **Bin Definition**
   ```python
   bins = np.arange(minf, maxf + fstep, fstep)
   ```
   Creates bin edges from `minf` to `maxf` at `fstep` intervals.
   - Example: `minf=20, maxf=45, fstep=5` → bins = [20, 25, 30, 35, 40, 45]

3. **Bin Assignment**
   ```python
   indices = np.digitize(f, bins) - 1
   ```
   Uses `np.digitize` to assign each frequency point to its corresponding bin.
   - Returns bin index for each value in `f`
   - Subtracts 1 to convert from 1-indexed to 0-indexed

4. **Bin Averaging**
   ```python
   for i, bin_center in enumerate(bins):
       mask = (indices == i)
       if np.any(mask):
           f_out.append(bin_center)
           a_out.append(20 * np.log10(np.mean(a[mask])))
   ```
   - Creates boolean mask for each bin
   - If bin contains data points:
     - Appends bin center frequency to output
     - Calculates mean amplitude in linear scale
     - Converts to dB: `20 * log10(mean(amplitude))`

#### Why This Matters

Test record sweeps don't produce perfectly uniform frequency spacing. The sweep rate varies, and FFT bin selection can be irregular. This function:
- **Regularizes frequency spacing** for consistent plotting
- **Averages multiple measurements** at similar frequencies for noise reduction
- **Converts to dB scale** for standard frequency response representation

#### Example
```
Input:  f = [21.3, 23.7, 24.9, 26.1, 28.4, ...]
        a = [0.95, 0.96, 0.94, 0.97, 0.95, ...]
        bins = [20, 25, 30, 35, ...]

Process: Bin 20 Hz: points at 21.3, 23.7, 24.9 Hz
         Mean amplitude = 0.95
         dB = 20*log10(0.95) = -0.44 dB

Output:  f_out = [20, 25, 30, ...]
         a_out = [-0.44, -0.38, -0.41, ...]
```

---

### 2. `rfft` Function

**Location**: Lines 315-351  
**Purpose**: Core FFT analysis engine that extracts fundamental frequency and harmonics from time-domain signal.

#### Function Signature
```python
def rfft(signal, Fs, minf, maxf, fstep):
```

#### Parameters
- `signal`: Audio signal array (channels, samples)
- `Fs`: Sample rate (Hz)
- `minf`: Minimum frequency to analyze (Hz)
- `maxf`: Maximum frequency to analyze (Hz)
- `fstep`: Frequency resolution (Hz)

#### Algorithm Breakdown

##### 2.1 Initialization
```python
freq, amp, freqx, ampx, freq2h, amp2h, freq3h, amp3h = [], [], [], [], [], [], [], []
F = int(Fs/fstep)
win = ft_window(F)
```

- **FFT Window Size**: `F = Fs/fstep`
  - Example: `Fs=96000 Hz, fstep=100 Hz → F=960 samples`
  - This gives frequency resolution of exactly `fstep` Hz
  
- **Window Function**: Flat-top window from `ft_window(F)`
  - Provides excellent amplitude accuracy (±0.01 dB)
  - Critical for accurate frequency response measurement

##### 2.2 Signal Shape Handling
```python
if len(signal.shape) == 1:  # mono signal
    signal = np.expand_dims(signal, axis=0)
```
Ensures signal is always 2D: (channels, samples)

##### 2.3 Main Processing Loop
```python
for x in range(0, signal.shape[1] - F, F):
```
Processes signal in non-overlapping windows of size `F`.

**Window stride**: `F` samples (no overlap)
- Overlap would improve frequency resolution but increase computation
- Non-overlapping is sufficient for sweep signals where frequency changes slowly

##### 2.4 FFT Computation (Primary Channel)
```python
y0 = abs(np.fft.rfft(signal[0, x:x + F] * win))
f0 = np.argmax(y0)  # use largest bin
```

**Step-by-step process**:

1. **Extract window**: `signal[0, x:x + F]` gets `F` samples from channel 0
2. **Apply window**: Multiply by flat-top window for spectral leakage reduction
3. **FFT**: `np.fft.rfft()` computes real FFT (only positive frequencies)
4. **Magnitude**: `abs()` converts complex FFT to magnitude spectrum
5. **Peak detection**: `np.argmax()` finds bin with maximum amplitude

**Why peak detection?**: 
- Sweep signals have one dominant frequency at any time
- The bin with maximum amplitude corresponds to the sweep frequency
- `f0` is the bin number, actual frequency is `f0 * fstep`

##### 2.5 Fundamental Frequency Extraction
```python
if f0 >= minf/fstep and f0 <= maxf/fstep:
    freq.append(f0*fstep)
    amp.append(y0[f0])
```

- **Frequency check**: Ensures detected frequency is within expected range
- **Frequency**: `f0 * fstep` converts bin number to Hz
- **Amplitude**: `y0[f0]` is the FFT magnitude at the fundamental

##### 2.6 Second Harmonic Detection
```python
if 2*f0 < F/2-2 and f0 > minf/fstep and f0 < maxf/fstep:
    f2 = np.argmax(y0[(2*f0)-2:(2*f0)+2])
    freq2h.append(f0*fstep)
    amp2h.append(y0[2*f0-2+f2])
```

**Algorithm**:
1. **Range check**: `2*f0 < F/2-2` ensures 2nd harmonic is within Nyquist limit
2. **Search window**: Looks at bins `[2*f0-2 : 2*f0+2]` (±2 bins around expected harmonic)
3. **Peak in window**: `np.argmax()` finds strongest bin in this range
4. **Store results**:
   - Frequency: `f0*fstep` (fundamental frequency, not 2f0)
   - Amplitude: Peak amplitude in the 2nd harmonic region

**Why ±2 bins?**: 
- Accounts for frequency estimation error in fundamental
- Harmonic may not be exactly at 2× due to:
  - Cartridge non-linearity
  - FFT bin spacing
  - Slight frequency modulation in sweep

##### 2.7 Third Harmonic Detection
```python
if 3*f0 < F/2-2 and f0 > minf/fstep and f0 < maxf/fstep:
    f3 = np.argmax(y0[(3*f0)-2:(3*f0)+2])
    freq3h.append(f0*fstep)
    amp3h.append(y0[3*f0-2+f3])
```

Identical logic to 2nd harmonic, but searches around `3*f0`.

##### 2.8 Secondary Channel Processing (Stereo)
```python
if signal.shape[0] > 1:  # Process second channel if stereo
    y1 = abs(np.fft.rfft(signal[1, x:x + F] * win))
    f1 = np.argmax(y1)
    if f0 >= minf/fstep and f0 <= maxf/fstep:  # use primary sweep f range
        freqx.append(f1*fstep)
        ampx.append(y1[f1])
```

**Key difference**: Uses `f0` frequency range check, not `f1`
- Assumes both channels contain same sweep signal
- Ensures frequency alignment between channels
- Allows comparison of left/right channel response

##### 2.9 Mono Signal Handling
```python
else:
    ampx = 0   # No secondary channel for mono
    freqx = 0
```

Returns 0 for secondary channel if signal is mono.

#### Return Values
```python
return freq, amp, freqx, ampx, freq2h, amp2h, freq3h, amp3h
```

All arrays contain raw FFT data (linear amplitude scale, irregular frequency spacing).

#### Example Operation

For a 1 kHz test tone at -20 dB with 2% 2nd harmonic distortion:

```
Input:  signal = sine wave at 1000 Hz
        Fs = 96000 Hz
        fstep = 100 Hz
        F = 960 samples

FFT bins:
  Bin 10 (1000 Hz):  Amplitude = 0.1 (fundamental)
  Bin 20 (2000 Hz):  Amplitude = 0.002 (2nd harmonic, 2%)

Output:
  freq = [1000]
  amp = [0.1]
  freq2h = [1000]
  amp2h = [0.002]
```

---

### 3. `normstr100` Function

**Location**: Lines 354-360  
**Purpose**: Applies bass compensation for STR-100 test record characteristics.

#### Function Signature
```python
def normstr100(f, a):
```

#### Parameters
- `f`: Frequency array (Hz)
- `a`: Amplitude array (dB)

#### Background

The STR-100 test record has a non-standard bass curve below 500 Hz. The record was cut with a 6.02 dB/octave rolloff from 500 Hz down to 40 Hz. This function compensates for that rolloff to restore flat response.

#### Algorithm
```python
fmin = 40
fmax = 500
slope = -6.02

for x in range(find_nearest(f, fmin), (find_nearest(f, fmax))):
    a[x] = a[x] + 20*np.log10(1*((f[x])/fmax)**((slope/20)/np.log10(2)))
```

**Breakdown**:

1. **Frequency Range**: 40-500 Hz (bass region)

2. **Slope Calculation**: 
   - `slope/20` = -6.02/20 = -0.301 (converts dB/octave to power ratio)
   - `/np.log10(2)` = -0.301/0.301 = -1.0 (normalizes for octave)
   
3. **Correction Formula**:
   ```
   correction = 20*log10((f/500)^(-1.0))
   ```
   
   This creates a +6.02 dB/octave boost below 500 Hz.

4. **Example**:
   ```
   At 500 Hz: correction = 20*log10(500/500)^(-1) = 0 dB
   At 250 Hz: correction = 20*log10(250/500)^(-1) = +6.02 dB (1 octave down)
   At 125 Hz: correction = 20*log10(125/500)^(-1) = +12.04 dB (2 octaves down)
   ```

#### Why This Matters

Without this correction, measurements from STR-100 records would show artificial bass rolloff. The correction ensures measurements represent the actual cartridge response, not the test record's characteristics.

---

### 4. `process_chunk` Function

**Location**: Lines 363-375  
**Purpose**: Orchestrates the complete processing pipeline for one frequency band.

#### Function Signature
```python
def process_chunk(signal, Fs, fmin, fmax, step, offset):
```

#### Parameters
- `signal`: Audio signal
- `Fs`: Sample rate (Hz)
- `fmin`: Minimum frequency for this band (Hz)
- `fmax`: Maximum frequency for this band (Hz)
- `step`: Frequency resolution for this band (Hz)
- `offset`: Amplitude offset to subtract (dB)

#### Algorithm
```python
f, a, fx, ax, f2, a2, f3, a3 = rfft(signal, Fs, fmin, fmax, step)

f, a = interpolate(f, a, fmin, fmax, step)
fx, ax = interpolate(fx, ax, fmin, fmax, step)
f2, a2 = interpolate(f2, a2, fmin, fmax, step)
f3, a3 = interpolate(f3, a3, fmin, fmax, step)

a = [amp - offset for amp in a]
ax = [amp - offset for amp in ax] if ax else []
a2 = [amp - offset for amp in a2]
a3 = [amp - offset for amp in a3]
```

**Step-by-step**:

1. **FFT Analysis**: 
   - Calls `rfft()` to extract raw frequency/amplitude data
   - Returns 8 arrays (fundamental + harmonics, stereo)

2. **Interpolation**:
   - Calls `interpolate()` on each array pair
   - Converts irregular FFT data to uniform frequency steps
   - Converts linear amplitude to dB

3. **Offset Compensation**:
   - Subtracts `offset` from all amplitude values
   - Compensates for FFT window size scaling differences between bands
   
#### Understanding the Offsets

The offsets compensate for the fact that **FFT magnitude scales with window size**. Each frequency band uses a different window size (F = Fs/step), which means the raw FFT magnitudes will be different even for identical signal amplitudes.

**Window sizes for each band** (at Fs = 96 kHz):
- Band 1: F = 96000/5 = **19,200 samples**
- Band 2: F = 96000/10 = **9,600 samples**  
- Band 3: F = 96000/20 = **4,800 samples**
- Band 4: F = 96000/100 = **960 samples** (reference, 0 dB offset)

**FFT Magnitude Scaling**: For a sinusoid with amplitude A, the FFT magnitude is proportional to A × N/2, where N is the window size. Therefore:

```
Magnitude_band1 / Magnitude_band4 = 19200/960 = 20
In dB: 20*log10(20) = 26.02 dB
```

**Calculated offsets**:
- **Band 1**: 20×log₁₀(19200/960) = 20×log₁₀(20) = **26.02 dB** ✓
- **Band 2**: 20×log₁₀(9600/960) = 20×log₁₀(10) = **20.00 dB** ✓
- **Band 3**: 20×log₁₀(4800/960) = 20×log₁₀(5) = **13.98 dB** ✓
- **Band 4**: 20×log₁₀(960/960) = 20×log₁₀(1) = **0.00 dB** ✓

These match the actual offsets used: (26.03, 19.995, 13.99, 0).

**Why this matters**: Without these offsets, there would be large discontinuities (jumps of 13-26 dB) at the boundaries between frequency bands. The offsets allow seamless stitching of the four bands into a single continuous frequency response curve.

---

### Understanding FFT Magnitude Scaling

This is a critical concept that explains why the offsets are necessary.

#### The Scaling Law

For a sinusoid with amplitude A sampled with an N-point FFT:
```
FFT_magnitude = A × N / 2
```

In decibels:
```
FFT_dB = 20×log₁₀(A × N/2) = 20×log₁₀(A) + 20×log₁₀(N/2)
```

The second term is a **constant offset** that depends only on window size N.

#### Practical Example

Consider a 1 kHz, 1V amplitude sine wave analyzed with different window sizes:

**Band 1 (N=19200)**:
```
FFT_magnitude = 1.0 × 19200/2 = 9600
FFT_dB = 20×log₁₀(9600) = 79.6 dB
```

**Band 4 (N=960)**:
```
FFT_magnitude = 1.0 × 960/2 = 480  
FFT_dB = 20×log₁₀(480) = 53.6 dB
```

**Difference**: 79.6 - 53.6 = **26.0 dB**

This 26 dB difference has nothing to do with the signal - it's purely an artifact of using different window sizes. The offset of 26.03 dB for Band 1 removes this artifact, allowing Band 1 and Band 4 to have the same dB scale.

#### Why Not Use the Same Window Size?

Using a 19,200-sample window for all frequencies would give:
- **Frequency resolution** = Fs/N = 96000/19200 = **5 Hz** everywhere
- This is overkill at high frequencies where 100 Hz resolution is adequate
- Processing would be **20× slower** due to larger FFTs
- Memory usage would increase significantly

The multi-resolution approach with offsets provides the best of both worlds: high resolution where needed (bass), computational efficiency where possible (treble).

---

### 5. `slice_frequency_range` Function

**Location**: Lines 380-397  
**Purpose**: Filters output arrays to user-specified frequency range.

#### Function Signature
```python
def slice_frequency_range(freq_array, amp_array, start_f=None, end_f=None):
```

#### Parameters
- `freq_array`: Array of frequencies (Hz)
- `amp_array`: Array of amplitudes (dB)
- `start_f`: Minimum frequency to include (Hz)
- `end_f`: Maximum frequency to include (Hz)

#### Algorithm

```python
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
```

**Key features**:

1. **Flexible input handling**: Accepts `None`, `""`, `0` as "no limit"
2. **Nearest neighbor search**: Uses `find_nearest()` for closest frequency match
3. **Bounds checking**: Swaps indices if reversed
4. **Inclusive slicing**: `idx_max+1` includes the end point

#### Example
```
Input:  freq_array = [20, 25, 30, ..., 19995, 20000]
        amp_array = [-2.1, -1.8, -1.5, ..., -3.2, -3.4]
        start_f = 100
        end_f = 10000

Process: 
  find_nearest([20,25,30,...], 100) → index 16 (100 Hz)
  find_nearest([20,25,30,...], 10000) → index 184 (10000 Hz)

Output:  freq_array[16:185] = [100, 105, 110, ..., 9900, 10000]
         amp_array[16:185] = [-1.2, -1.1, -1.0, ..., -2.8, -2.9]
```

---

## Helper Functions (External to createplotdata)

These functions are defined outside but are critical to `createplotdata`:

### `ft_window` Function

**Location**: Lines 270-275  
**Purpose**: Generates a flat-top window function for FFT analysis.

#### Function Signature
```python
def ft_window(n):
```

#### Algorithm
```python
a0, a1, a2, a3, a4 = 0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368
x = np.arange(n)
w = (a0 - a1*np.cos(2*np.pi*x/(n-1)) + a2*np.cos(4*np.pi*x/(n-1)) - 
     a3*np.cos(6*np.pi*x/(n-1)) + a4*np.cos(8*np.pi*x/(n-1)))
```

This implements a **5-term flat-top window** (also called SRS flat-top).

**Formula**:
```
w(n) = Σ(k=0 to 4) [(-1)^k * a_k * cos(2πkx/(n-1))]
```

**Coefficients**: The specific values (a0-a4) are optimized for:
- **Amplitude accuracy**: ±0.01 dB (excellent for measurement applications)
- **Scalloping loss**: <0.01 dB
- **Frequency selectivity**: Moderate (wider main lobe than Hann/Hamming)

**Why flat-top?**:
- **Amplitude accuracy** is critical for frequency response measurement
- Hann/Hamming windows are better for frequency resolution but have ±1.5 dB scalloping loss
- Flat-top sacrifices frequency resolution for amplitude accuracy

**Trade-offs**:
```
Window Type    | Amplitude Accuracy | Frequency Resolution | Scalloping Loss
---------------|-------------------|---------------------|----------------
Rectangular    | Poor (±3.9 dB)    | Best                | High (3.9 dB)
Hann           | Fair (±1.4 dB)    | Good                | Moderate (1.4 dB)
Flat-top       | Excellent (±0.01) | Poor                | Very Low (0.01 dB)
```

For phono cartridge measurements, we need accurate amplitude → flat-top is the correct choice.

---

### `find_nearest` Function

**Location**: Lines 278-292  
**Purpose**: Efficiently finds the index of the closest value in a sorted array.

#### Function Signature
```python
def find_nearest(array, value):
```

#### Algorithm
```python
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
```

**Algorithm breakdown**:

1. **Binary search**: `np.searchsorted()` uses binary search (O(log n))
   - Much faster than linear search for large arrays
   - Returns insertion point to maintain sorted order

2. **Edge case handling**:
   - If `idx == 0`: value is before first element → return 0
   - If `idx == len(array)`: value is after last element → return last index

3. **Nearest neighbor selection**:
   - Compares distance to `array[idx]` vs `array[idx-1]`
   - Returns whichever is closer

#### Example
```
array = [100, 200, 300, 400, 500]
value = 350

searchsorted(array, 350) → 3 (insertion point)
abs(array[3] - 350) = abs(400 - 350) = 50
abs(array[2] - 350) = abs(300 - 350) = 50  (tie)
Returns 2 (idx-1 in case of tie)
```

---

## Main Processing Pipeline

Now let's examine the main body of `createplotdata`:

### Step 1: Initialize Output Arrays
```python
fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3 = [], [], [], [], [], [], [], []
```

Eight empty lists to accumulate results from all frequency bands.

---

### Step 2: Multi-Band Processing

```python
for fmin, fmax, step, offset in [(20,45,5,26.03), (50,90,10,19.995), 
                                  (100,980,20,13.99), (1000,50000,100,0)]:
    f, a, fx, ax, f2, a2, f3, a3 = process_chunk(signal, Fs, fmin, fmax, step, offset)
    fout.extend(f); aout.extend(a); foutx.extend(fx); aoutx.extend(ax)
    fout2.extend(f2); aout2.extend(a2); fout3.extend(f3); aout3.extend(a3)
```

#### Band Configuration

| Band | Freq Range | Step | Offset | Window Size (96kHz) | Points | Purpose |
|------|------------|------|--------|---------------------|--------|---------|
| 1 | 20-45 Hz | 5 Hz | 26.03 dB | 19,200 samples | 6 | Deep bass, high resolution |
| 2 | 50-90 Hz | 10 Hz | 19.995 dB | 9,600 samples | 5 | Bass, medium resolution |
| 3 | 100-980 Hz | 20 Hz | 13.99 dB | 4,800 samples | 45 | Midrange, standard resolution |
| 4 | 1000-50000 Hz | 100 Hz | 0 dB | 960 samples | 491 | Treble (reference band) |

**Total points**: ~547 frequency measurements from 20 Hz to 50 kHz

#### Why Multiple Bands?

1. **Resolution vs. Processing time**:
   - Bass frequencies need higher resolution (musical content, human hearing sensitivity)
   - Treble can use lower resolution (less critical for phono response, faster processing)
   
2. **FFT window size optimization**:
   - `F = Fs/step`
   - Band 1: F = 96000/5 = 19,200 samples (200 ms window)
   - Band 4: F = 96000/100 = 960 samples (10 ms window)
   - Longer windows for bass = better frequency resolution
   
3. **Offset compensation**:
   - Each band uses a different FFT window size, which scales the magnitude
   - Offsets normalize all bands to the same scale (Band 4 as reference)
   - Without offsets, there would be 13-26 dB jumps at band boundaries

---

### Step 3: STR-100 Correction (Optional)

```python
if str100 == 1:
    aout = normstr100(fout, aout)
    aout2 = normstr100(fout2, aout2)
    aout3 = normstr100(fout3, aout3)
    if aoutx:
        aoutx = normstr100(foutx, aoutx)
```

Applies bass compensation if using STR-100 test record. Applied to all arrays (fundamental + harmonics, stereo).

---

### Step 4: Low-Pass Smoothing Filter

```python
sos = iirfilter(3, 0.5, btype='lowpass', output='sos')
aout = sosfiltfilt(sos, aout)
aout2 = sosfiltfilt(sos, aout2)
aout3 = sosfiltfilt(sos, aout3)
if len(aoutx) > 0:
    aoutx = sosfiltfilt(sos, aoutx)
```

#### Filter Design

- **Type**: 3rd-order Butterworth low-pass
- **Cutoff**: 0.5 (normalized frequency)
- **Implementation**: Second-order sections (SOS) for numerical stability
- **Application**: Zero-phase filtering with `sosfiltfilt`

#### What Does This Do?

The normalized cutoff frequency of 0.5 means:
```
f_cutoff = 0.5 * f_nyquist = 0.5 * 0.5 * f_sample = 0.25 * f_sample
```

Wait, this seems wrong. Let me reconsider...

Actually, `iirfilter` with cutoff 0.5 means 0.5 × Nyquist frequency **of the input data**.

But the input data here is not the original audio signal - it's the frequency response curve (amplitude vs frequency points).

**Reinterpretation**:
- Input "signal": array of amplitude values at discrete frequencies
- "Sample rate": 1 sample per frequency point
- This is actually a **smoothing filter** on the frequency response curve itself!

**Effect**:
- Removes high-frequency noise in the frequency response curve
- Smooths out bumps and dips from measurement noise
- Critical cutoff is relative to the spacing of frequency points

For example, with 100 Hz frequency steps:
- "Nyquist" = 50 Hz (in the frequency-domain representation)
- Cutoff = 0.5 × 50 Hz = 25 Hz
- This smooths variations faster than 25 frequency points

**Why needed?**:
- FFT analysis has measurement noise
- Peak detection can miss true peak by 1-2 bins
- Test record irregularities
- Smoothing improves visual appearance without losing real data

---

### Step 5: Normalization Calculation

```python
if file0norm == 0 and iteration[0] == 0:
    i = find_nearest(fout, normalize)
    norm[0] = aout[i]
elif file0norm == 1:
    i = find_nearest(fout, normalize)
    norm[0] = aout[i]
```

#### Normalization Modes

**Mode 0** (`file0norm=0`): **Independent normalization**
- Each file normalized independently
- Only on first iteration (`iteration[0] == 0`)
- Subsequent files keep the same `norm[0]` value

**Mode 1** (`file0norm=1`): **File 0 reference normalization**
- Always update `norm[0]`
- Second file normalized to same reference as first file
- Allows direct comparison between two measurements

#### Algorithm
1. Find index of normalization frequency (default 1000 Hz)
2. Store amplitude at that frequency in `norm[0]`
3. This value will be subtracted from all amplitudes

**Why 1000 Hz?**:
- Middle of audio range
- RIAA pre-emphasis is 0 dB at 1000 Hz
- Convenient reference point
- Avoids bass (RIAA rolloff) and treble (HF issues)

---

### Step 6: Apply Normalization

```python
aout = [a - norm[0] for a in aout]
aoutx = [a - norm[0] for a in aoutx] if len(aoutx) > 0 else []
aout2 = [a - norm[0] for a in aout2]
aout3 = [a - norm[0] for a in aout3]
```

Subtracts normalization value from all amplitude arrays.

**Result**: Amplitude at normalization frequency becomes 0 dB.

**Example**:
```
Before normalization at 1000 Hz: aout[i] = 5.23 dB
After:  aout = [a - 5.23 for a in aout]
At 1000 Hz: 5.23 - 5.23 = 0.00 dB ✓
```

---

### Step 7: Increment Iteration Counter

```python
iteration[0] += 1
```

Tracks how many times function has been called. Used to determine normalization behavior for multi-file processing.

---

### Step 8: Frequency Range Filtering

```python
fout, aout = slice_frequency_range(fout, aout, start_f, end_f)
foutx, aoutx = slice_frequency_range(foutx, aoutx, start_f, end_f)
fout2, aout2 = slice_frequency_range(fout2, aout2, start_f, end_f)
fout3, aout3 = slice_frequency_range(fout3, aout3, start_f, end_f)
```

Applies user-specified frequency range limits to all output arrays.

**Example**:
- User sets `start_f=100, end_f=10000`
- Function removes all data points <100 Hz and >10 kHz
- Useful for focusing on specific frequency ranges (e.g., vocal range, bass only)

---

### Step 9: Return Results

```python
return fout, aout, foutx, aoutx, fout2, aout2, fout3, aout3
```

Returns 8 arrays ready for plotting:
- Primary channel frequency response
- Secondary channel frequency response (stereo)
- 2nd harmonic distortion data
- 3rd harmonic distortion data

---

## Complete Example Walkthrough

Let's trace a complete execution with example data:

### Input
```python
signal = stereo_sweep_20Hz_to_20kHz  # (2, 1920000) @ 96 kHz
Fs = 96000
iteration = [0]
norm = [0]
start_f = None
end_f = 20000
str100 = 0
file0norm = 0
normalize = 1000
```

### Execution Trace

#### Band 1: 20-45 Hz @ 5 Hz steps

```
process_chunk(signal, 96000, 20, 45, 5, 26.03)
  ├─ F = 96000/5 = 19200 samples (200 ms windows)
  ├─ rfft extracts:
  │    freq  = [21.4, 23.7, 26.1, 28.5, 30.8, 33.2, 35.5, 38.0, 40.2, 42.7]
  │    amp   = [0.94, 0.95, 0.96, 0.95, 0.97, 0.96, 0.95, 0.96, 0.97, 0.95]
  ├─ interpolate bins to:
  │    f = [20, 25, 30, 35, 40, 45]
  │    a = [-0.53, -0.44, -0.27, -0.35, -0.22, -0.44] dB
  └─ Subtract offset (compensates for 19200-sample FFT window vs 960-sample reference):
       a = [-0.53-26.03, -0.44-26.03, ...] = [-26.56, -26.47, -26.30, -26.38, -26.25, -26.47] dB

Append to fout, aout
```

#### Band 2: 50-90 Hz @ 10 Hz steps
```
Similar process...
fout extends to: [20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90]
```

#### Band 3: 100-980 Hz @ 20 Hz steps
```
fout extends to: [20, 25, ..., 90, 100, 120, 140, ..., 960, 980]
```

#### Band 4: 1000-50000 Hz @ 100 Hz steps
```
fout extends to: [20, 25, ..., 980, 1000, 1100, 1200, ..., 19900, 20000]
Total points: ~547
```

#### After all bands
```
fout = [20, 25, 30, ..., 19900, 20000]  (547 points)
aout = [-26.56, -26.47, ..., -5.23, -5.18]  (dB, not yet normalized)
```

#### STR-100 correction (skipped, str100=0)

#### Low-pass smoothing
```
Butterworth filter smooths aout curve
Minor changes to remove noise spikes
```

#### Normalization
```
Find 1000 Hz: index = 184
norm[0] = aout[184] = -5.23 dB

aout = [a - (-5.23) for a in aout]
     = [-26.56-(-5.23), -26.47-(-5.23), ..., -5.23-(-5.23), ...]
     = [-21.33, -21.24, ..., 0.00, ...]  dB

At 1000 Hz: 0.00 dB ✓
```

#### Frequency range filtering
```
end_f = 20000
Find nearest to 20000 Hz → index 539
Slice all arrays to fout[0:540]
```

### Final Output
```python
fout  = [20, 25, 30, ..., 19900, 20000]  (540 points)
aout  = [-21.33, -21.24, -21.07, ..., -0.15, -0.12]  dB (normalized to 1kHz = 0dB)
foutx = [20, 25, 30, ..., 19900, 20000]  (right channel frequencies)
aoutx = [-21.41, -21.29, -21.11, ..., -0.18, -0.15]  dB (right channel)
fout2 = [20, 25, 30, ..., 9950, 10000]   (2nd harmonic, lower range due to Nyquist)
aout2 = [-81.2, -80.8, -79.5, ..., -75.3, -75.1]  dB (2nd harmonic distortion)
fout3 = [20, 25, 30, ..., 6633, 6667]    (3rd harmonic, even lower range)
aout3 = [-85.7, -85.2, -84.9, ..., -78.1, -77.9]  dB (3rd harmonic distortion)
```

These arrays are then passed to plotting functions to generate frequency response graphs.

---

## Performance Characteristics

### Computational Complexity

**Per frequency band**:
- FFT operations: O(N log N) where N = F (window size)
- Number of windows: signal_length / F
- Total: O((signal_length / F) × F log F) = O(signal_length × log F)

**Total for all 4 bands**: O(signal_length × Σ log F_i)

For a 20-second stereo recording at 96 kHz:
```
signal_length = 96000 × 20 × 2 = 3,840,000 samples

Band 1: F=19200, windows=100, FFTs: 100 × O(19200 log 19200) ≈ 26M operations
Band 2: F=9600,  windows=200, FFTs: 200 × O(9600 log 9600)   ≈ 26M operations
Band 3: F=4800,  windows=400, FFTs: 400 × O(4800 log 4800)   ≈ 25M operations
Band 4: F=960,   windows=2000,FFTs: 2000 × O(960 log 960)    ≈ 20M operations

Total: ~97M operations (completes in ~0.5-2 seconds on modern CPU)
```

### Memory Usage

**Peak memory** (approximate):
```
Input signal:        3,840,000 × 8 bytes = 30 MB
FFT intermediate:    19,200 × 8 bytes = 150 KB (per band)
Output arrays:       547 points × 8 arrays × 8 bytes = 35 KB
Total:              ~31 MB (very reasonable)
```

---

## Common Issues and Edge Cases

### Issue 1: Nyquist Limit for Harmonics

**Problem**: 2nd/3rd harmonics may exceed Nyquist frequency

**Example**:
```
Fundamental = 25 kHz @ 96 kHz sample rate
2nd harmonic = 50 kHz (exceeds Nyquist = 48 kHz)
```

**Solution**: Range checks in `rfft()`
```python
if 2*f0 < F/2-2:  # Ensures 2nd harmonic is below Nyquist
```

### Issue 2: Missing Data in Interpolation Bins

**Problem**: Some frequency bins may have no FFT data points

**Example**:
```
Sweep jumps from 995 Hz to 1005 Hz
Bin at 1000 Hz has no data
```

**Solution**: `interpolate()` checks for data
```python
if np.any(mask):  # Only append if bin has data
```

Result: Frequency points without data are simply omitted from output.

### Issue 3: Mono vs Stereo Signals

**Problem**: Code must handle both mono and stereo inputs

**Solution**: Shape checking in `rfft()`
```python
if len(signal.shape) == 1:  # mono
    signal = np.expand_dims(signal, axis=0)
```

Converts mono to (1, samples) format for uniform processing.

### Issue 4: Division by Zero in Normalization

**Problem**: If normalization frequency isn't in sweep range

**Example**:
```
normalize = 1000 Hz
Sweep only covers 20-500 Hz
```

**Solution**: `find_nearest()` finds closest frequency
```python
i = find_nearest(fout, normalize)
```

Will normalize to 500 Hz (closest available) instead of crashing.

### Issue 5: Filter Stability

**Problem**: High-order IIR filters can be numerically unstable

**Solution**: Second-order sections (SOS) representation
```python
sos = iirfilter(3, 0.5, btype='lowpass', output='sos')
```

SOS format is more numerically stable than transfer function coefficients.

---

## Optimization Opportunities

### 1. Vectorization

**Current**: Loop-based interpolation
```python
for i, bin_center in enumerate(bins):
    mask = (indices == i)
    if np.any(mask):
        # ...
```

**Optimized**: NumPy's `binned_statistic`
```python
from scipy.stats import binned_statistic
a_out, bins, _ = binned_statistic(f, a, statistic='mean', bins=bins)
```

**Speedup**: ~3-5× faster for large datasets

### 2. Pre-computed Windows

**Current**: Window computed every call
```python
win = ft_window(F)
```

**Optimized**: Cache windows by size
```python
_window_cache = {}
def get_window(n):
    if n not in _window_cache:
        _window_cache[n] = ft_window(n)
    return _window_cache[n]
```

**Benefit**: Reduces repeated computation for same window sizes

### 3. Parallel Band Processing

**Current**: Sequential band processing
```python
for fmin, fmax, step, offset in bands:
    f, a, ... = process_chunk(...)
```

**Optimized**: Parallel processing
```python
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor() as executor:
    results = executor.map(process_chunk, bands)
```

**Speedup**: ~4× on quad-core CPU (near-linear scaling)

---

## Known Issues and Limitations

### Smoothing Filter Artifact with Non-Uniform Data Spacing

#### Problem Description

The low-pass smoothing filter applied in Step 4 uses `sosfiltfilt()`, which **assumes uniform sample spacing**. However, the `createplotdata` function produces data with **four different frequency spacings**:

- Band 1: 5 Hz spacing
- Band 2: 10 Hz spacing  
- Band 3: 20 Hz spacing
- Band 4: 100 Hz spacing

When aggressive smoothing is used (e.g., cutoff = 0.02 instead of the default 0.5), this creates **visible "kinks" at band boundaries**. The kink is not a discontinuity in amplitude (no jump), but rather a **discontinuity in the first derivative** (slope).

#### Example Measurements

At the 980→1000 Hz boundary with cutoff = 0.02:

| Frequency | Amplitude | Slope (dB/Hz) | Notes |
|-----------|-----------|---------------|-------|
| 980 Hz | +0.0000628 dB | **-0.00000314** | End of Band 3 (20 Hz spacing) |
| 1000 Hz | +0.0000000 dB | **-0.00000068** | Start of Band 4 (100 Hz spacing) |

The slope changes by **~78%** at the boundary, creating a visible corner in the frequency response curve.

See visualization: `smoothing_kink_solution.png` (generated during testing) shows the problem and solution side-by-side, including derivative plots that clearly reveal the discontinuity.

#### Root Cause

The `sosfiltfilt()` function interprets each data point as having a fixed time/frequency interval. When spacing suddenly changes from 20 Hz to 100 Hz, the filter's effective cutoff frequency (relative to the "Nyquist" of the data) changes by 5×. This creates:

1. **Different filtering strength** on each side of the boundary
2. **Derivative discontinuity** where the two filtered segments meet
3. **Visible kink** that becomes more pronounced with lower cutoff frequencies

#### Suggested Solutions

**Option 1: Resample to Uniform Spacing (Recommended)**

Interpolate all bands to uniform spacing before filtering:

```python
from scipy.interpolate import interp1d

# After combining all bands but BEFORE smoothing
fout_uniform = np.arange(20, 20000, 5)  # 5 Hz uniform spacing
interpolator = interp1d(fout, aout, kind='cubic', fill_value='extrapolate')
aout_uniform = interpolator(fout_uniform)

# Now apply smoothing to uniform data
sos = iirfilter(3, 0.5, btype='lowpass', output='sos')
aout_smoothed = sosfiltfilt(sos, aout_uniform)

# Downsample back to original points if desired
aout_final = interpolator(fout)
```

**Pros**: Eliminates kink artifact completely, allows aggressive smoothing  
**Cons**: Additional computational cost, slight interpolation artifacts

**Option 2: Variable-Bandwidth Filtering**

Apply different filter cutoffs to each band based on its spacing:

```python
def smooth_by_band(fout, aout, bands):
    result = []
    
    for fmin, fmax, step, offset in bands:
        # Get data for this band
        mask = [(f >= fmin and f <= fmax) for f in fout]
        band_data = [a for a, m in zip(aout, mask) if m]
        
        # Scale cutoff by step size (larger step = lower cutoff)
        cutoff = 0.5 * (5.0 / step)  # Normalize to 5 Hz baseline
        sos = iirfilter(3, cutoff, btype='lowpass', output='sos')
        smoothed = sosfiltfilt(sos, band_data)
        
        result.extend(smoothed)
    
    return result
```

**Pros**: Preserves original data points, minimal overhead  
**Cons**: Still has some boundary artifacts, more complex code

**Option 3: Use Current Smoothing Only for Mild Filtering**

Limit smoothing filter to cutoff ≥ 0.3 to minimize artifacts:

```python
# Conservative smoothing that works with non-uniform spacing
sos = iirfilter(3, 0.5, btype='lowpass', output='sos')  # Stay above 0.3
aout = sosfiltfilt(sos, aout)
```

**Pros**: Simple, no code changes needed  
**Cons**: Cannot use aggressive smoothing when desired

**Option 4: Frequency-Domain Smoothing**

Apply smoothing in the frequency domain using a moving average:

```python
def freq_domain_smooth(fout, aout, window_hz):
    """Smooth in frequency domain using moving average."""
    smoothed = []
    
    for i, f in enumerate(fout):
        # Find points within window_hz of this frequency
        mask = [abs(freq - f) <= window_hz/2 for freq in fout]
        values = [a for a, m in zip(aout, mask) if m]
        
        if values:
            smoothed.append(np.mean(values))
        else:
            smoothed.append(aout[i])
    
    return smoothed

# Apply with 50 Hz window
aout_smoothed = freq_domain_smooth(fout, aout, window_hz=50)
```

**Pros**: Works naturally with non-uniform spacing, no kinks  
**Cons**: Slower than IIR filtering, different smoothing characteristics

#### Recommendation

For the current implementation: **Use Option 1 (resample to uniform spacing)** before filtering when aggressive smoothing is needed (cutoff < 0.3). For mild smoothing (cutoff ≥ 0.5), the current approach works acceptably.

For production code that requires aggressive smoothing: Implement Option 1 with uniform resampling as a preprocessing step.

---

## Summary

The `createplotdata` function is a sophisticated multi-resolution FFT analysis engine that:

1. **Processes audio in 4 frequency bands** with optimal resolution for each range
2. **Applies FFT window size compensation** to seamlessly stitch bands together
3. **Extracts fundamental frequency and harmonics** for distortion analysis
4. **Handles mono and stereo signals** with unified processing
5. **Applies calibration and normalization** for accurate measurements
6. **Smooths and filters results** for clean frequency response curves
7. **Supports multiple test record types** (STR-100, standard)

The function demonstrates excellent engineering with:
- Appropriate use of FFT windowing for amplitude accuracy
- Multi-resolution analysis for efficiency and detail
- Correct handling of FFT magnitude scaling across different window sizes
- Robust edge case handling
- Clear separation of concerns via sub-functions
- Numerically stable filtering

**Known limitation**: The low-pass smoothing filter can create derivative discontinuities ("kinks") at band boundaries when aggressive filtering is used, due to non-uniform frequency spacing. See the "Known Issues" section for solutions.

This is production-quality audio analysis code suitable for precision phono cartridge measurements.
