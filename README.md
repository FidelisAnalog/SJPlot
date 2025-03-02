# SJPlot
18.3.8

## Overview
This python script was originally conceived by Scott Wurcer as a tool to accurately plot the frequency response of phono cartridges using the logarithmic sweep tracks found on common (and some not so common) test records.

## Features
- **Multiple Data Sets**: Frequency response, 2nd and 3rd harmonic distortion, and crosstalk. 
- **Mono or Stereo Files**: For stereo files, the Left channel is assumed to be the tone fundamental, and the Right channel the crosstalk.
- **Automatic Sweep Extraction**: For certain test records, the sweeps can be automatically extracted from a single file.
- **RIAA Processing**: Ability to apply RIAA bass and treble processing separately or together, along with inverse RIAA. 
- **STR-100 Support**: Correction for the constant velocity characteristic specific to the CBS STR-100 test record.
- **XG-7001 Support**: Correction of the custom bass EQ of this Denon test record.
- **Custom Normalization**: Ability to choose at which frequency to set the 0dB reference for the plot, and the ability to normalize both channels individually or to the same level as the first channel.
- **Custom Start/Stop points**: Choose to plot the entire sweep or to start at 1kHz, and/or the highest frequency to plot.
- **Multiple Plot Styles**: Choose between traditional, dual-axis, dual frequency response and distortion, dual frequency response zoom above dual axis, or a small plot of only frequency response.  

## Requirements
- Python 3
- NumPy
- SciPy
- Matplotlib

## Installation
1. Ensure Python 3 is installed on your system.
2. Install the required Python libraries using pip:

```bash
pip install numpy scipy matplotlib
```

3. Download the latest version of SJPlot.py and SJPlot.cfg from the respository, and place them in the directory that will contain the wav files to process. This directory is also where the plot images will be saved, in addition to extracted sweeps, if chosen. 

## Usage
There are several options to provide the captured audio to the script:
  - If your sweep record is [listed in this table](https://github.com/FidelisAnalog/SJPlot/?tab=readme-ov-file#supported-test-records-for-sweep-extraction), you can provide a single stereo file that is from a few seconds before the first pilot tone, to a few seconds past the end of the second sweep, without any edits between. The script can automatically extract the sweeps from the file for processing.
  - You can manually process the audio and provide either one or two files to the script. This audio file must not have any "silent" parts - it must begin at the start of the sweep and end when the sweep stops. If you want to plot the crosstalk these files must be stereo, otherwise they can be mono.
  - These files may be 16 or 24 bit wav and up to 96kHz sampling rate if you want to use the script's built-in RIAA filters. If you don't need to use the built-in RIAA filters, they can be up to 384kHz.  

## Configuration

The script configuration may be provided by a configuration file (default: SJPlot.cfg) or via the command line. The configuration precedence works in the following order:

  - **Default values**: These are the built-in defaults, hardcoded into the script.
  - **Configuration file**: If you provide a configuration file, the values in that file will override the default values.
  - **Command-line arguments**: These take the highest precedence. If a command-line argument is provided, it will override both the default and the config file values.

For clarity, the configuraiton precdence is command-line arguments first, then the configuration file values, and last the hard-coded default values.

### Configuration Parameters

| **Parameter**       | **Default** | **Description**                                                   |
|---------------------| :---: |-------------------------------------------------------------------|
| file_0           | |The first (L) file to plot, or the only file to plot, or the file you want to extract sweeps from. |
| file_1           | |The second (R) file to plot. If using one file, leave this blank. If you're extracting sweeps, this parameter is ignored. |
| plot_info        | |Alpha-numeric entries separated by " / ". The script will save a PNG file named from the plot_info argument, replacing " / " with "_". For example, "Cart / Load / Record" will create a file named "Cart_Load_Record.png". |
| equip_info       | |This argument is placed on the bottom left of the plot image to describe the capture chain. The recommended format is "Arm -> Phonostage -> ADC". |
| extract_sweeps   |`False`|`True`: extract the sweeps from **INPUT_FILE_0**<br>`False`: do not process the file for extraction of sweeps.<br> |
| save_sweeps      |`False`|`True`: save the extracted sweeps<br>`False`: do not save files |
| test_record      | |If extracting sweeps, specify what test record the audio was captured from. [Supported records can be found here](https://github.com/FidelisAnalog/SJPlot/tree/Splitter?tab=readme-ov-file#supported-test-records-for-sweep-extraction). |
| plot_style       |`4`|`1`: traditional<br>`2`: dual axis (twinx)<br>`3`: dual plot FR and distortion<br>`4`: dual plot FR zoom and dual axis (twinx)<br>`5`: small plot FR only |
| file0norm        |`False`|`True`: normalize both files to file_0 level, shown as a magenta "x" on the plot<br>`False`: normalize both files independently, shown as a magenta line on the plot |
| end_f            |`20000`|Highest frequency to plot in Hz.                                                |
| onekfstart       |`False`|`True`: start plot from 1 kHz<br>`False`: disable                               |
| normalize        |`1000`|Frequency in Hz to set as 0dB in the plot                                      |
| riaa_mode        |`2`|`0`: none<br>`1`: bass emphasis<br>`2`: treble de-emphasis<br>`3`: both               |
| riaa_inverse     |`True`|`True`: inverse RIAA EQ per **riaa_mode** setting<br>`False`: disable            |
| str100           |`False`|`True`: enable 6dB/oct correction from 500Hz to 40Hz<br>`False`: disable         |
| xg7001           |`False`|`True`: custom bass filter for Denon XG-7001 sweep (stereoplay filter)<br>`False`: disable |
| plot_data_out    |`False`|`True`: output the plot data to the console<br>`False`: disable                  |
| log_level        |`info`|`info`: standard logging level<br>`debug`: verbose logging intended for debugging issues. |
| version          | |Command-line only - output sofware version and exit. |
| help             | |Command-line only - display the help contents and exit. |
| config           | |Command-line only - use an alternate configuration file. | 



### Default Configuration File Parameters
The configuration file is in INI format, and must be in the same directory the script is run from. You can download the default configuation file `SJPlot.cfg` from the repository. 

```ini
[Files to Process]
file_0 = 
file_1 =

[Metadata]
plot_info = Cart / Load / Record
equip_info = Arm -> Phonostage -> ADC

[Sweep Extraction]
extract_sweeps = false
save_sweeps = false
test_record = 

[Plot Parameters]
plot_style = 4
file0norm = false
end_f = 20000
onekfstart = false
normalize = 1000

[Audio Processing]
riaa_mode = 2
riaa_inverse = true
str100 = false
xg7001 = false

[For Geeks]
plot_data_out = false
log_level = info
```


### Command-Line Arguments
Command-line arguments will override default parameters, and any parameters in the config file.  In fact, you can use the script with only the command-line and omit the configuration file entirely.  The command-line parameters are the same as listed in the Configuraiton Parameters table above, except the for the command-line they are prefixed with "--", and then followed by a space before the argument. 

NOTE: For boolean (True/False) arguments on the command-line, you can only pass the argument without a value, which will make it True.  For example, to enable save_sweeps, you'd only pass `--save_sweeps`.

### Running the Script
To run the script without any commnand-line arguments using the default configuration file:
```bash
python sjplot.py
```


To run the script from the command-line, using the default configuration file but with command line arguments to extract sweeps from a capture of an STR-100 test record:
```bash
python sjplot.py --file_0 MyAudioFile.wav --extract_sweeps --test_record STR100
```


To run the script using an alternate configuration file:
```bash
python sjplot.py --config someotherconfig.cfg
```

If the argument you're passing has spaces or special characters in it, you'll need to capture it in quotes:
```bash
python sjplot.py --plot_info "Some Cart / Some Load / STR-100"
```


## Supported Test Records for Sweep Extraction

| **Test Record** | **Parameter** | **Description** |
|-----------------| :---: |-----------------|
| TRS-1007        | `TRS1007`     | JVC/Victor - Frequency Response Test 20Hz-20kHz |
| CA-TRS-1007     | `TRS1007`     | clearaudio - Frequency Response Test Record 20Hz - 20kHz |
| TRS-1005        | `TRS1005`     | JVC/Victor - High Frequency Response Test 1kHz - 50kHz |
| STR-100         | `STR100`      | CBS Laboratories - Professional Test Record (40Hz - 20kHz) |
| STR-120         | `STR120`      | CBS Laboratories - Wide Range Pickup Test (500Hz - 50kHz) |
| STR-130         | `STR130`      | CBS Laboratories - RIAA System Response Test (40Hz - 20kHz) |
| STR-170         | `STR170`      | CBS Laboratories - 318-Microsecond Frequency Response Test (40Hz - 20kHz) |
| QR 2009         | `QR2009`      | Brüel & Kjær - Stereophonic Gliding Frequency Record 20-20 000 Hz |
| QR 2010         | `QR2010`      | Brüel & Kjær - Stereo Test Record 5 Hz - 45 kHz |
| XG-7001         | `XG7001`      | Denon - Denon Technical Test Record (20Hz - 20kHz) |
| XG-7002         | `XG7002`      | Denon - Denon Audio Technical Test Record - Pick Up Test I (1kHz - 50kHz) |
| XG-7005         | `XG7005`      | Denon - Denon Audio Technical Test Record - RIAA System Test (20Hz - 20kHz) |
| DIN 45 543      |  `DIN45543`   | DIN - Frequenzgang - Und Übersprech-Mess-Schallplatte (20Hz - 20kHz) |


## Example Output

<br/>
<div align="center" style="padding: 20px 0;">
    <img src="images/figure_1.png" alt="Example Plot.">
    <p><b>Figure 1 - Plot Style 1</b></p>
    <p>"Traditional" plot with a single x-axis.</p>
</div>
<br/>

<br/>
<div align="center" style="padding: 20px 0;">
    <img src="images/figure_2.png" alt="Example Plot.">
    <p><b>Figure 2 - Plot Style 2</b></p>
    <p>Dual-axis (twin-x) plot with Amplitude on the left x-axis, and Distortion on the right x-axis.</p>
</div>
<br/>

<br/>
<div align="center" style="padding: 20px 0;">
    <img src="images/figure_3.png" alt="Example Plot.">
    <p><b>Figure 3 - Plot Style 3</b></p>
    <p>Dual plot with Amplitude in the upper plot, and distortion in the lower plot. This plot does not show cross-talk.</p>
</div>
<br/>

<br/>
<div align="center" style="padding: 20px 0;">
    <img src="images/figure_4.png" alt="Example Plot.">
    <p><b>Figure 4 - Plot Style 4</b></p>
    <p>Dual plot with zoomed-in frequency response in the upper plot, and the lower plot being dual-axis as in style 2.  This is the default and recommended plot style to use.</p>
</div>
<br/>

<br/>
<div align="center" style="padding: 20px 0;">
    <img src="images/figure_5.png" alt="Example Plot.">
    <p><b>Figure 5 - Plot Style 5</b></p>
    <p>Zoomed-in frequency response only plot.</p>
</div>
<br/>



## How It Works
Usual FFT packages aren't the right tool to plot these sweep tracks. There are two primary issues: First, due to the test signal being a logarithmic sweep, the plot will have a 6dB/octave slope.  Second, any energy in the signal will be integrated in to the plot, including undesirable signals. The first issue can be solved by doing an RTA or fractional octave smoothing, the latter of which has consequences.  However, the second issue is more difficult to overcome as the test signal cannot be synchronized with the measurement.   

To solve for both issues, the script perfoms FFTs on sequential time-slices of the signal, taking the highest level at the desired measurement frequency (instantaneous frequency measurement).  Multiple measurements of the same frequency are averaged, and the plot data is thus created.  This method mirrors the behavior of the chart recorders for which these test tracks were intended. 


## Contributing
Contributions to improve the script are welcome. Please feel free to fork the repository, make your changes, and submit a pull request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.


