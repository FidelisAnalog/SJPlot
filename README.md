# SJPlot

## Overview
This python script was originally conceived by Scott Wurcer as a tool to 

## Features
- **Channel Selection**: Choose between left, right, or mixed audio channels for analysis.
- **Peak Detection**: Automatically detects the highest peaks in the audio signal to determine the time intervals between successive revolutions.
- **RPM Calculation**: Calculates the RPM based on the time intervals between peaks.
- **Statistical Analysis**: Provides minimum, maximum, average, and standard deviation for both time intervals and RPM values.
- **Twin Axis RPM and Time Interval Visualization Plot**: Provides for enhanced comparative analysis of time intervals and RPM on a single graph.

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

## Usage
1. Directly record the output of your turntable with the stylus looping in a a dead-end groove (i.e. the end of the LP side) in stereo with a sound card (line input).
2. Save the audio file in WAV format.
3. Run the script from the command line, providing the path to your audio file, the number of clicks (peaks) included in your audio file, the minimum expected distance between clicks in milliseconds, and optionally the channel mode (`left`, `right`, or `mix`). Here's how you can do it:

```bash
python3 rpm.py [-h] [--channel_mode {left,right,mix}] [--plot] [--plot_title PLOT_TITLE] filename num_peaks min_distance_ms
```

Example Command:

```bash
python3 rpm.py /path/to/your/audio.wav 45 1300 --channel_mode left
```



## How It Works

A dead-end groove on an LP normally contains a well defined 'click' or 'pop' as the stylus passes by the entry groove. This script precisely measures the time between each click to
derive the precise RPM that the turntable platter is rotating at. A sound card must be used to capture a WAV file for the rpm.py script to post-process. It does not currently have real time analysis. No special LP is needed for this test, as all LPs contain
at least one dead-end groove at the end of a side. Some turntables auto-stop at the end of the LP side not allowing for these clicks to be recorded. In that case, an LP with a dead-end groove prior to the LP run out groove must be used. An example of that
would be the CBS STR-100 test record, where some tracks (bands) end with a dead-end groove to prevent the stylus from advancing to the next test track.  This script was tested specifically using the <b>CBS STR-100 </b> (issue 3) test LP, Band 3B.  After testing several
LP dead-end grooves, it was determined that the CBS STR-100 produced clean clicks that were more easily detected.  Not all dead-end grooves produce a sufficiently defined click that rises well above the surface noise of the LP.  This is why two parameters of
the script include the number of expected clicks and a minimum expected distance between those clicks.  This is to give the script enough of a hint to easily identify the target clicks.  If it cannot, then it will display a message.
It is also possible that some stylus profiles (ex. conical, elliptical),  phono preamps with limited headroom and/or certain LPs might not produce a well defined click peak that can be accurately analyzed. Another advantage of using the CBS STR-100 LP is that
the dead-end groove chosen can normally be closer to the null point of the stylus, depending on your particular cartridge alignment. This can result in a click with less distortion components, which can improve the captured click waveform.  

You can use any bitrate and sampling rate.  You must record in 2 channel stereo mode.  The script currently expects stereo, because it provides more flexibility for analysis. Using a higher sampling rate increases the precision of the calculations.
For instance a sample rate of 48Khz results in a resolution of 0.0000052083 seconds per sample.  192Khz is 0.000001302075 seconds per sample. This results in a very precise timing of RPM, far beyond any other commonly available method. You must make
a recording via direct sound card connection (no microphones), as a high resolution capture is required.

The other variable is 'channel_mode' which can select the left, right or stereo (mix) channel(s) for analysis.  In testing, the 'left' channel normally produces the best result from a click. If this doesn't work, the 'right' channel can be used. If
that doesn't work, 'mix' can be used. Mix mixes the two channels into mono (in phase). This aggregation might be needed to get analysis working, but it might be slightly less accurate than using a single channel. In the event that none of these methods work,
it means that your equipment or test LP isn't providing a clean enough peak for the script to detect precise timing.

While not required, we recommend normalizing the WAV file to 0 dB, using software such as Audacity. Normalizing in Audacity has the benefit in that you can clearly visualize the clicks and the noise floor within Audacity to make sure you have captured
something usable. We recommend saving the file with a name which indicates the number of clicks included, so that you do not have to remember or count them when you run the script, remembering that you must specify the number of peaks value to the script as an argument.
You should also include the speed you used (33 or 45) as well, since the minimum expected distance must be specified according to the usage.

<br/>
<div align="center" style="padding: 20px 0;">
    <img src="images/audacity.png" alt="Audacity screenshot showing captured WAV file">
    <p><b>Audacity showing captured normalized, stereo WAV file. Clicks are clearly visible.</b></p>
</div>
<br/>

The longer your recorded sample, the more accuracy you will have regarding average speed over time, as well as variance. For the most part, 1 minute of sampling should be enough and is a good sample for comparison. (1 minute of sampling,  33 1/3 RPM  = ~ 35 clicks & 45 RPM = ~ 45 clicks)

The script calculates the minimum, maximum, average and standard deviation of each rotation in seconds, as well as in RPM. Because this calculation is made at
the same azimuth point each revolution, it cannot calculate flutter, which would rely on a continuous measurement of turntable speed. Rather these measurements are a precise averaging of speed over 1 revolution which would give an idea of wow. Ultimately, it should still
serve as a precise way to set turntable speed. It might be possible to take measurements by changing the record's azimuth orientation on the the platter and making a collection of measurements at a variation of angles to expose different rpm characteristics, which might show
up as a variance at a specific azimuth that is far different than the others. Another advantage of this method of measuring RPM is that it includes stylus friction normally incurred while playing an LP, not encountered when using strobe discs. 

Output will be directed to standard out. <i>Note that when reading the output, the minimal time interval produces the maximum RPM, the the maximum interval produces the minimal RPM. RPM statistics are derived by first converting each time interval into an RPM value. This process preserves the highest level of precision by accounting for the non-linear relationship between time intervals and RPM. Specifically, RPM is calculated as the inverse of the time interval (with RPM = 60 / Time Interval), reflecting how shorter intervals correspond to higher RPMs and vice versa. By calculating RPM values from individual intervals before computing statistics, we ensure that these statistics accurately represent the RPM distribution, taking the non-linear dynamics of this conversion into full account. </i>

Here is an example:

```
python3 rpm.py ~/c45rpm45.wav 45 1300 --channel_mode left

Channel mode: left
Revolutions: 44

Statistic            Time Intervals (s)                  RPM Values
------------------------------------------------------------------------------------------
Min                  1.333208333333331552                44.998418024366408474
Max                  1.333380208333331041                45.004219145544958280
Average              1.333293678977272911                45.001338466409144701
Std Dev              0.000060313472201144                0.002035699504200471
```

There is another option where you can run the script with the --plot option to get a twin-axis plot visualizing both time intervals between peaks and their corresponding RPM (Revolutions Per Minute) on a single graph. This twin-axis plot provides a comprehensive view of the audio analysis, allowing users to easily compare the time intervals and RPMs, which can be particularly useful for understanding variations in the turntable's speed. To utilize this feature, simply add --plot when running the script, as shown below:

```bash
python3 rpm.py python your_script_name.py your_audio_file.wav number_of_peaks minimum_distance_ms  --plot --plot_title "Your Custom Plot Title"
```
This will generate a twin-axis plot, where one axis represents the time intervals between successive peaks (in seconds), and the other axis shows the calculated RPM values. The plot is saved as a PNG file in the same directory as the input audio file, named with the prefix of the audio file followed by "_RPM_Analysis_Plot.png". Additionally, if your environment supports displaying plots, the plot will also be shown interactively. Remember, the --plot option is entirely optional and should be used when visual insights into the RPM analysis are desired. It's an excellent tool for visually diagnosing the performance and consistency of your turntable or any other rotating machinery analyzed through audio signals.

<br/>
<div align="center" style="padding: 20px 0;">
    <img src="images/fivem2_RPM_Analysis_Plot.png" alt="Generated twin-axis plot">
    <p><b>Generated twin-axis plot.</b></p>
</div>
<br/>
 
## Community and Support

Join a vibrant community to discuss the Turntable RPM Analysis script, share your results, ask questions, and connect with fellow audiophiles and hobbyists. Whether you're looking to troubleshoot an issue, share insights, or simply learn more about turntable performance analysis, the Audio Science Review forum is the place to be.

### Join the Discussion

We've established a dedicated thread on [Audio Science Review](https://www.audiosciencereview.com/) for all things related to the Turntable RPM Analysis script. This is a fantastic opportunity to engage with a community of like-minded individuals passionate about audio equipment and analysis.

**What to Expect in the Forum:**
- **Share Your Results**: Post your RPM analysis findings and see how they compare with others'.
- **Get Help and Advice**: Encounter an issue? Looking for tips? The community and the developers are here to help.
- **Provide Feedback**: Your suggestions can help improve the script for everyone. Don't hesitate to share your thoughts.

**Direct Link to the Discussion Thread**: Dive into the conversation through this permalink: [Turntable RPM Analysis Discussion Thread](https://www.audiosciencereview.com/forum/index.php?threads/turntable-rpm-measurement-script.52586/)

Your participation helps make our tool better for everyone. We look forward to seeing your contributions and discussions!


## Contributing
Contributions to improve the script are welcome. Please feel free to fork the repository, make your changes, and submit a pull request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.


