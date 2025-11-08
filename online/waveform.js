/**
 * Waveform Renderer Module
 * Parses WAV files and renders stereo waveform to canvas WITHOUT resampling
 * Preserves full high-frequency detail at native sample rate
 */

/**
 * Parse WAV file header and extract audio data
 * @param {Uint8Array} bytes - WAV file bytes
 * @returns {Object} - {sampleRate, channels, bitDepth, leftChannel, rightChannel}
 */
function parseWAV(bytes) {
    const dataView = new DataView(bytes.buffer);
    
    // Verify RIFF header
    const riff = String.fromCharCode(...bytes.slice(0, 4));
    if (riff !== 'RIFF') {
        throw new Error('Not a valid WAV file (missing RIFF header)');
    }
    
    // Verify WAVE format
    const wave = String.fromCharCode(...bytes.slice(8, 12));
    if (wave !== 'WAVE') {
        throw new Error('Not a valid WAV file (missing WAVE format)');
    }
    
    // Find fmt chunk
    let offset = 12;
    let fmtChunkSize = 0;
    let sampleRate = 0;
    let channels = 0;
    let bitDepth = 0;
    
    while (offset < bytes.length) {
        const chunkId = String.fromCharCode(...bytes.slice(offset, offset + 4));
        const chunkSize = dataView.getUint32(offset + 4, true);
        
        if (chunkId === 'fmt ') {
            fmtChunkSize = chunkSize;
            const audioFormat = dataView.getUint16(offset + 8, true);
            channels = dataView.getUint16(offset + 10, true);
            sampleRate = dataView.getUint32(offset + 12, true);
            bitDepth = dataView.getUint16(offset + 22, true);
            
            if (audioFormat !== 1) {
                throw new Error('Only PCM WAV files are supported');
            }
            
            offset += 8 + chunkSize;
        } else if (chunkId === 'data') {
            // Found data chunk - extract samples
            const dataOffset = offset + 8;
            const dataSize = chunkSize;
            const bytesPerSample = bitDepth / 8;
            const numSamples = dataSize / (bytesPerSample * channels);
            
            const leftChannel = new Float32Array(numSamples);
            const rightChannel = channels === 2 ? new Float32Array(numSamples) : null;
            
            // Read samples based on bit depth
            for (let i = 0; i < numSamples; i++) {
                const sampleOffset = dataOffset + i * bytesPerSample * channels;
                
                if (bitDepth === 16) {
                    // 16-bit PCM
                    leftChannel[i] = dataView.getInt16(sampleOffset, true) / 32768.0;
                    if (channels === 2) {
                        rightChannel[i] = dataView.getInt16(sampleOffset + 2, true) / 32768.0;
                    }
                } else if (bitDepth === 24) {
                    // 24-bit PCM (3 bytes)
                    const left24 = (dataView.getUint8(sampleOffset) |
                                   (dataView.getUint8(sampleOffset + 1) << 8) |
                                   (dataView.getUint8(sampleOffset + 2) << 16));
                    // Sign extend
                    leftChannel[i] = (left24 & 0x800000 ? left24 - 0x1000000 : left24) / 8388608.0;
                    
                    if (channels === 2) {
                        const right24 = (dataView.getUint8(sampleOffset + 3) |
                                        (dataView.getUint8(sampleOffset + 4) << 8) |
                                        (dataView.getUint8(sampleOffset + 5) << 16));
                        rightChannel[i] = (right24 & 0x800000 ? right24 - 0x1000000 : right24) / 8388608.0;
                    }
                } else if (bitDepth === 32) {
                    // 32-bit PCM
                    leftChannel[i] = dataView.getInt32(sampleOffset, true) / 2147483648.0;
                    if (channels === 2) {
                        rightChannel[i] = dataView.getInt32(sampleOffset + 4, true) / 2147483648.0;
                    }
                } else {
                    throw new Error(`Unsupported bit depth: ${bitDepth}`);
                }
            }
            
            return {
                sampleRate,
                channels,
                bitDepth,
                leftChannel,
                rightChannel: rightChannel || leftChannel // Use left for mono
            };
        } else {
            // Skip unknown chunk
            offset += 8 + chunkSize;
        }
    }
    
    throw new Error('No data chunk found in WAV file');
}

/**
 * Downsample audio data for display (preserve peaks)
 * @param {Float32Array} samples - Audio samples
 * @param {number} targetPoints - Number of points to display
 * @returns {Object} - {data: Array of {min, max}, peakAmplitude: number}
 */
function downsampleForDisplay(samples, targetPoints) {
    const samplesPerPoint = Math.floor(samples.length / targetPoints);
    const result = [];
    let globalMax = 0;
    
    for (let i = 0; i < targetPoints; i++) {
        const start = i * samplesPerPoint;
        const end = Math.min(start + samplesPerPoint, samples.length);
        
        let min = samples[start];
        let max = samples[start];
        
        for (let j = start; j < end; j++) {
            if (samples[j] < min) min = samples[j];
            if (samples[j] > max) max = samples[j];
        }
        
        result.push({ min, max });
        
        // Track global peak for normalization
        globalMax = Math.max(globalMax, Math.abs(min), Math.abs(max));
    }
    
    return { data: result, peakAmplitude: globalMax };
}

/**
 * Draw waveform to canvas
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array} waveformData - Array of {min, max} values
 * @param {number} peakAmplitude - Peak amplitude for normalization
 * @param {string} color - Waveform color
 */
function drawWaveform(canvas, waveformData, peakAmplitude, color) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const halfHeight = height / 2;
    
    // Use actual peak amplitude for scaling (zoom to fit)
    const scale = peakAmplitude > 0 ? 1.0 / peakAmplitude : 1.0;
    
    // Fill background with white
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);
    
    // Draw waveform bars
    ctx.fillStyle = color;
    const barWidth = width / waveformData.length;
    
    for (let i = 0; i < waveformData.length; i++) {
        const { min, max } = waveformData[i];
        
        // Scale to canvas coordinates with amplitude zoom
        const yTop = halfHeight - (max * scale * halfHeight);
        const yBottom = halfHeight - (min * scale * halfHeight);
        const barHeight = Math.max(1, yBottom - yTop);
        
        ctx.fillRect(i * barWidth, yTop, Math.ceil(barWidth), barHeight);
    }
    
    // Draw center line
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.15)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, halfHeight);
    ctx.lineTo(width, halfHeight);
    ctx.stroke();
}

/**
 * Draw timeline/time axis
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {number} durationSeconds - Total duration in seconds
 */
function drawTimeline(canvas, durationSeconds) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Fill background with white
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);
    
    // Determine appropriate time interval for major ticks
    let majorInterval, minorInterval, labelInterval;
    if (durationSeconds <= 5) {
        majorInterval = 0.5;
        minorInterval = 0.1;
        labelInterval = 0.5;
    } else if (durationSeconds <= 10) {
        majorInterval = 1;
        minorInterval = 0.5;
        labelInterval = 1;
    } else if (durationSeconds <= 30) {
        majorInterval = 5;
        minorInterval = 1;
        labelInterval = 5;
    } else if (durationSeconds <= 60) {
        majorInterval = 5;
        minorInterval = 1;
        labelInterval = 5;
    } else if (durationSeconds <= 120) {
        majorInterval = 5;
        minorInterval = 1;
        labelInterval = 5;
    } else if (durationSeconds <= 300) {
        majorInterval = 10;
        minorInterval = 2;
        labelInterval = 5;  // Show labels every 5s even with 10s major ticks
    } else {
        majorInterval = 10;
        minorInterval = 2;
        labelInterval = 5;  // Show labels every 5s
    }
    
    const pixelsPerSecond = width / durationSeconds;
    
    // Draw minor ticks first
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    for (let t = 0; t <= durationSeconds; t += minorInterval) {
        if (t % majorInterval !== 0) {
            const x = Math.round(t * pixelsPerSecond);
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, 4);
            ctx.stroke();
        }
    }
    
    // Draw major ticks and labels
    ctx.strokeStyle = '#666';
    ctx.fillStyle = '#666';
    ctx.font = '14px monospace';  // Increased from 13px
    ctx.textAlign = 'center';
    
    // Draw major ticks
    for (let t = 0; t <= durationSeconds; t += majorInterval) {
        const x = Math.round(t * pixelsPerSecond);
        
        // Draw major tick mark
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, 8);
        ctx.stroke();
    }
    
    // Draw labels (may be different interval than major ticks)
    for (let t = 0; t <= durationSeconds; t += labelInterval) {
        const x = Math.round(t * pixelsPerSecond);
        
        // Format time label
        let label;
        if (t < 1) {
            label = `${(t * 1000).toFixed(0)}ms`;
        } else if (t < 60) {
            label = `${t}s`;
        } else {
            const minutes = Math.floor(t / 60);
            const seconds = (t % 60).toFixed(0).padStart(2, '0');
            label = `${minutes}:${seconds}`;
        }
        
        ctx.fillText(label, x, 20);
    }
}

/**
 * Render stereo waveform to container
 * @param {string} containerId - ID of container element
 * @param {Uint8Array} wavBytes - WAV file bytes
 * @returns {Promise<void>}
 */
export async function renderWaveform(containerId, wavBytes) {
    const container = document.getElementById(containerId);
    if (!container) {
        throw new Error(`Container element not found: ${containerId}`);
    }
    
    try {
        // Parse WAV file
        const audioData = parseWAV(wavBytes);
        const durationSeconds = audioData.leftChannel.length / audioData.sampleRate;
        
        console.log(`WAV: ${audioData.sampleRate}Hz, ${audioData.bitDepth}-bit, ${audioData.channels} channel(s), ${durationSeconds.toFixed(2)}s`);
        
        // Create wrapper HTML - all in one box styled like traceback
        const waveformHtml = `
            <div style="position:relative; margin-top:15px; padding:10px; background:#fff; border-radius:4px; border:1px solid #ddd;">
                <div style="font-size:0.75em; color:#666; margin-bottom:10px;">Audio Waveform (${audioData.sampleRate}Hz, ${audioData.bitDepth}-bit, ${audioData.channels}ch, ${durationSeconds.toFixed(1)}s)</div>
                <button id="copy-waveform-btn" 
                        style="position:absolute; top:5px; right:40px; padding:6px 10px; background:rgba(255,255,255,0.9); color:#333; border:none; border-radius:4px; cursor:pointer; font-size:0.85em; display:flex; align-items:center; transition:opacity 0.2s;" 
                        title="Copy waveform to clipboard">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2"/>
                        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                    </svg>
                </button>
                <button id="download-waveform-btn" 
                        style="position:absolute; top:5px; right:5px; padding:6px 10px; background:rgba(255,255,255,0.9); color:#333; border:none; border-radius:4px; cursor:pointer; font-size:0.85em; display:flex; align-items:center; transition:opacity 0.2s;" 
                        title="Download waveform as PNG">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                        <polyline points="7,10 12,15 17,10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                </button>
                <canvas id="waveform-left" style="width:100%; height:100px; display:block; background:#fff;"></canvas>
                ${audioData.channels === 2 ? `
                    <canvas id="waveform-right" style="width:100%; height:100px; display:block; margin-top:2px; background:#fff;"></canvas>
                ` : ''}
                <canvas id="waveform-timeline" style="width:100%; height:30px; display:block; margin-top:5px; background:#fff;"></canvas>
            </div>
        `;
        container.innerHTML = waveformHtml;
        
        // Get canvas elements
        const leftCanvas = document.getElementById('waveform-left');
        const rightCanvas = document.getElementById('waveform-right');
        const timelineCanvas = document.getElementById('waveform-timeline');
        
        // Render at fixed width for consistent image quality (scales with CSS)
        const RENDER_WIDTH = 1000;  // Reduced from 1600 for smaller file sizes
        const dpr = window.devicePixelRatio || 1;
        
        // Setup left channel canvas
        leftCanvas.width = RENDER_WIDTH * dpr;
        leftCanvas.height = 100 * dpr;
        
        // Setup right channel canvas
        if (rightCanvas) {
            rightCanvas.width = RENDER_WIDTH * dpr;
            rightCanvas.height = 100 * dpr;
        }
        
        // Setup timeline canvas
        timelineCanvas.width = RENDER_WIDTH * dpr;
        timelineCanvas.height = 30 * dpr;
        
        // Downsample for display (preserve peaks and get peak amplitude)
        const targetPoints = RENDER_WIDTH;
        const leftResult = downsampleForDisplay(audioData.leftChannel, targetPoints);
        const rightResult = downsampleForDisplay(audioData.rightChannel, targetPoints);
        
        // Use the larger peak for consistent scaling across channels
        const globalPeak = Math.max(leftResult.peakAmplitude, rightResult.peakAmplitude);
        
        console.log(`Peak amplitude: ${globalPeak.toFixed(4)} (${(globalPeak * 100).toFixed(1)}% of full scale)`);
        
        // Draw waveforms with amplitude zoom
        drawWaveform(leftCanvas, leftResult.data, globalPeak, '#667eea');
        if (rightCanvas) {
            drawWaveform(rightCanvas, rightResult.data, globalPeak, '#764ba2');
        }
        
        // Draw timeline
        drawTimeline(timelineCanvas, durationSeconds);
        
        // Setup download button
        const downloadBtn = document.getElementById('download-waveform-btn');
        downloadBtn.addEventListener('click', () => {
            // Visual feedback
            downloadBtn.style.opacity = '0.6';
            setTimeout(() => downloadBtn.style.opacity = '1', 200);
            
            downloadWaveformImage(leftCanvas, rightCanvas, timelineCanvas, audioData, durationSeconds);
        });
        
        // Setup copy button
        const copyBtn = document.getElementById('copy-waveform-btn');
        copyBtn.addEventListener('click', async () => {
            // Visual feedback
            copyBtn.style.opacity = '0.6';
            setTimeout(() => copyBtn.style.opacity = '1', 200);
            
            await copyWaveformImage(leftCanvas, rightCanvas, timelineCanvas, audioData, durationSeconds);
        });
        
        console.log('Waveform rendered successfully (no resampling)');
        
    } catch (error) {
        console.error('Error rendering waveform:', error);
        container.innerHTML = `<p style="color:#c62828;padding:10px;">Unable to display waveform: ${error.message}</p>`;
        throw error;
    }
}

/**
 * Download waveform as PNG image
 * @param {HTMLCanvasElement} leftCanvas - Left channel canvas
 * @param {HTMLCanvasElement} rightCanvas - Right channel canvas (or null for mono)
 * @param {HTMLCanvasElement} timelineCanvas - Timeline canvas
 * @param {Object} audioData - Audio data with metadata
 * @param {number} durationSeconds - Duration in seconds
 */
function downloadWaveformImage(leftCanvas, rightCanvas, timelineCanvas, audioData, durationSeconds) {
    try {
        // Create composite canvas
        const headerSize = 14 * (window.devicePixelRatio || 1) + 20;  // Font size + spacing
        const totalHeight = leftCanvas.height + (rightCanvas ? rightCanvas.height + 2 : 0) + timelineCanvas.height + 5 + headerSize;
        const compositeCanvas = document.createElement('canvas');
        compositeCanvas.width = leftCanvas.width;
        compositeCanvas.height = totalHeight;
        
        const ctx = compositeCanvas.getContext('2d');
        
        // White background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, compositeCanvas.width, compositeCanvas.height);
        
        // Draw header text
        ctx.fillStyle = '#333';
        const headerFontSize = 14 * (window.devicePixelRatio || 1);  // Reduced from 24px
        ctx.font = `${headerFontSize}px sans-serif`;
        ctx.textAlign = 'left';
        ctx.fillText(
            `Input Audio Waveform - ${audioData.sampleRate}Hz, ${audioData.bitDepth}-bit, ${audioData.channels}ch, ${durationSeconds.toFixed(1)}s`,
            10,
            headerFontSize + 10
        );
        
        // Draw canvases
        let yOffset = headerFontSize + 20;  // Reduced spacing
        ctx.drawImage(leftCanvas, 0, yOffset);
        yOffset += leftCanvas.height;
        
        if (rightCanvas) {
            yOffset += 2;
            ctx.drawImage(rightCanvas, 0, yOffset);
            yOffset += rightCanvas.height;
        }
        
        yOffset += 5;
        ctx.drawImage(timelineCanvas, 0, yOffset);
        
        // Convert to blob and download
        compositeCanvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
            link.download = `waveform-${audioData.sampleRate}Hz-${timestamp}.png`;
            link.href = url;
            link.click();
            URL.revokeObjectURL(url);
            console.log('Waveform image downloaded');
        }, 'image/png');
        
    } catch (error) {
        console.error('Error downloading waveform:', error);
        alert('Failed to download waveform image');
    }
}

/**
 * Copy waveform image to clipboard
 * @param {HTMLCanvasElement} leftCanvas - Left channel canvas
 * @param {HTMLCanvasElement} rightCanvas - Right channel canvas (or null for mono)
 * @param {HTMLCanvasElement} timelineCanvas - Timeline canvas
 * @param {Object} audioData - Audio data with metadata
 * @param {number} durationSeconds - Duration in seconds
 */
async function copyWaveformImage(leftCanvas, rightCanvas, timelineCanvas, audioData, durationSeconds) {
    try {
        // Check if clipboard API is available
        if (!navigator.clipboard || !navigator.clipboard.write) {
            alert('Clipboard API not supported in this browser. Try using the download button instead.');
            return;
        }
        
        // Create composite canvas (same as download)
        const headerSize = 14 * (window.devicePixelRatio || 1) + 20;
        const totalHeight = leftCanvas.height + (rightCanvas ? rightCanvas.height + 2 : 0) + timelineCanvas.height + 5 + headerSize;
        const compositeCanvas = document.createElement('canvas');
        compositeCanvas.width = leftCanvas.width;
        compositeCanvas.height = totalHeight;
        
        const ctx = compositeCanvas.getContext('2d');
        
        // White background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, compositeCanvas.width, compositeCanvas.height);
        
        // Draw header text
        ctx.fillStyle = '#333';
        const headerFontSize = 14 * (window.devicePixelRatio || 1);
        ctx.font = `${headerFontSize}px sans-serif`;
        ctx.textAlign = 'left';
        ctx.fillText(
            `Input Audio Waveform - ${audioData.sampleRate}Hz, ${audioData.bitDepth}-bit, ${audioData.channels}ch, ${durationSeconds.toFixed(1)}s`,
            10,
            headerFontSize + 10
        );
        
        // Draw canvases
        let yOffset = headerFontSize + 20;
        ctx.drawImage(leftCanvas, 0, yOffset);
        yOffset += leftCanvas.height;
        
        if (rightCanvas) {
            yOffset += 2;
            ctx.drawImage(rightCanvas, 0, yOffset);
            yOffset += rightCanvas.height;
        }
        
        yOffset += 5;
        ctx.drawImage(timelineCanvas, 0, yOffset);
        
        // Safari requires ClipboardItem to be created synchronously,
        // but the blob can be a Promise that resolves later
        await navigator.clipboard.write([
            new ClipboardItem({
                'image/png': new Promise((resolve, reject) => {
                    compositeCanvas.toBlob((blob) => {
                        if (blob) {
                            resolve(blob);
                        } else {
                            reject(new Error('Failed to create blob'));
                        }
                    }, 'image/png');
                })
            })
        ]);
        
        console.log('Waveform image copied to clipboard');
        
    } catch (error) {
        console.error('Error copying waveform:', error);
        alert('Failed to copy image to clipboard. Try the download button instead.');
    }
}
