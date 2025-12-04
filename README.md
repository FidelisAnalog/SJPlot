# SJPlot v19

Phono cartridge frequency response measurement tool. Analyzes test record sweep recordings and generates frequency response plots with crosstalk and harmonic distortion.

## Download 

[Download v19 Alpha-1 Release](https://github.com/FidelisAnalog/SJPlot/releases/tag/v19.0.0-alpha.1)

## Usage

```bash
python SJPlot.py config.json
```

## Configuration File

JSON format.

### Example

```json
{
  "plot_info": "Cartridge / Load / Record",
  "equip_info": "Arm -> Phonostage -> ADC",
  "author": "Name",
  
  "files": [
    {"path": "recording.wav", "label": ""}
  ],
  
  "mode": "standard",
  "style": 4,
  "dimensions": ["fundamental", "crosstalk", "h2", "h3"],
  
  "extract_sweeps": true,
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
  
  "plot_data_out": false,
  "log_level": "info"
}
```

---

## Options Reference

### Plot Labeling

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `plot_info` | string | "Cart / Load / Record" | Plot title |
| `equip_info` | string | "Arm -> Phonostage -> ADC" | Footer left text |
| `author` | string | "" | Footer right text |

### Input Files

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `files` | array | [] | List of file objects |

Each file object:
```json
{"path": "path/to/file.wav", "label": "optional label"}
```

- `path`: Path to WAV file
- `label`: Display label for comparison mode. If empty, filename is used.

### Mode and Style

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mode` | string | "standard" | `"standard"` or `"comparison"` |
| `style` | int | 4 | Plot layout (1-5) |
| `dimensions` | array | ["fundamental", "crosstalk", "h2", "h3"] | Data to plot (comparison mode) |

**Modes:**
- `standard`: Single file analysis with L/R channels. Style determines layout.
- `comparison`: Multiple files overlaid. Uses `dimensions` to select what to plot.

**Styles:**
| Style | Layout | Description |
|-------|--------|-------------|
| 1 | single panel | Fundamental, crosstalk, h2, h3 all on same axis |
| 2 | single panel + twin axis | Fundamental + crosstalk on left axis, harmonics on right axis |
| 3 | dual panel (50/50) | Fundamental on top, harmonics on bottom (no crosstalk) |
| 4 | dual panel (1:2 ratio) + twin | Fundamental overview on top, full detail on bottom with harmonics on twin axis |
| 5 | compact single panel | Fundamental only, tight y-limits, short height |

**Dimensions** (for comparison mode):
- `"fundamental"` - Frequency response
- `"crosstalk"` - Channel separation
- `"h2"` - 2nd harmonic distortion
- `"h3"` - 3rd harmonic distortion

### Sweep Extraction

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `extract_sweeps` | bool | false | Extract sweeps from full-side recording |
| `extract_channel` | string | "both" | `"left"`, `"right"`, or `"both"` |
| `test_record` | string | "STR100" | Test record type |

**Supported test records:**
`STR100`, `STR120`, `STR130`, `STR170`, `TRS1005`, `TRS1007`, `QR2009`, `QR2010`, `XG7001`, `XG7002`

When `extract_sweeps` is false, input files should be pre-extracted sweep WAVs.

### Normalization

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `normalize` | int/null | 1000 | Frequency (Hz) to normalize to 0dB. null = no normalization. |
| `normalize_mode` | string | "relative" | `"relative"` or `"absolute"` |

**Normalization modes:**
- `relative`: All files normalized to first file's level at normalize frequency. Shows relative differences.
- `absolute`: Each file normalized to its own level at normalize frequency. Shows absolute response.

### Frequency Range and Smoothing

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `start_f` | int/null | null | Start frequency (Hz). null = use data minimum. |
| `end_f` | int/null | null | End frequency (Hz). null = use data maximum. |
| `smoothing` | float | 0.5 | Data smoothig filter low pass cutoff. |
| `override_ylim` | array/null | null | Force y-axis limits as [min, max]. null = auto. |

### Corrections

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `riaa_mode` | int | 0 | RIAA equalization: 0=off, 1=bass, 2=treble, 3=both |
| `riaa_inverse` | bool | false | true=emphasis, false=de-emphasis |

`str100` and `xg7001` correction flags are auto-set based on `test_record`.

### Output

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `plot_data_out` | bool | false | Export plot data to CSV (not yet implemented) |
| `log_level` | string | "info" | `"debug"`, `"info"`, `"warning"`, `"error"` |

---

## Output

Saves PNG file named from `plot_info` value.

## Requirements

- Python 3.8+
- NumPy
- SciPy  
- Matplotlib
- myhifi_lib (bundled)
