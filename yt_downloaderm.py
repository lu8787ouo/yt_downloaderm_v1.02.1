'''
ver1.02.1
'''

import os
import re
import subprocess
import threading
from pytubefix import YouTube, Playlist
from tkinter import filedialog
from tkinter.messagebox import showinfo, showerror
from PIL import Image, ImageTk
import requests
from io import BytesIO

def toggle_time_inputs(is_playlist_var, process_option, start_time_label, start_time_entry, end_time_label, end_time_entry):
    if is_playlist_var.get() or process_option.get() == 'none':
        start_time_label.place_forget()
        start_time_entry.place_forget()
        end_time_label.place_forget()
        end_time_entry.place_forget()
    else:
        start_time_label.place(x=50, y=410)
        start_time_entry.place(x=190, y=410)
        end_time_label.place(x=350, y=410)
        end_time_entry.place(x=470, y=410)

def update_progress_label(text, progress_label, window):
    progress_label.config(text=text)
    progress_label.update_idletasks()
    label_width = progress_label.winfo_width()
    center_x = (window.winfo_width() - label_width) // 2
    progress_label.place(x=center_x, y=500)

def select_save_path(save_path_var):
    path = filedialog.askdirectory()
    save_path_var.set(path)

def is_valid_time_format(time_str):
    # 使用正则表达式检查时间格式
    pattern = re.compile(r'^\d{2}:\d{2}:\d{2}$')
    if not pattern.match(time_str):
        return False
    
    # 检查小时、分钟和秒数的范围
    parts = time_str.split(':')
    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    if hours < 0 or hours > 23:
        return False
    if minutes < 0 or minutes > 59:
        return False
    if seconds < 0 or seconds > 59:
        return False
    
    return True

def fetch_thumbnail(video):
    thumbnail_url = video.thumbnail_url
    response = requests.get(thumbnail_url)
    img_data = response.content
    img = Image.open(BytesIO(img_data))
    img = img.resize((256, 162), Image.LANCZOS)  # 調整縮圖大小以適應窗口
    return ImageTk.PhotoImage(img)

def is_playlist_url(url):
    return 'list=' in url

def search_resolution_func(video_link, is_playlist_var, video_resolution, logo_label, start_time_entry, end_time_entry):
    if video_link == '':
        showerror(title='Error', message='Provide the video link please!')
    else:
        if is_playlist_var.get():
            if is_playlist_url(video_link):
                pl = Playlist(video_link)
                video = pl.videos[0]
                thumbnail_image = fetch_thumbnail(video)
                logo_label.config(image=thumbnail_image)
                logo_label.image = thumbnail_image

                video_resolution['values'] = ['The Best Resolution']
                showinfo(title='Search Complete', message='Check the Combobox for the available video resolutions')
            else:
                showerror(title='Error', message='The provided URL is not a valid playlist.')
        else:
            try:
                video = YouTube(video_link)
                thumbnail_image = fetch_thumbnail(video)
                logo_label.config(image=thumbnail_image)
                logo_label.image = thumbnail_image

                video_length = video.length
                start_time_entry.delete(0, 'end')
                end_time_entry.delete(0, 'end')
                start_time_entry.insert(0, "00:00:00")
                end_time_entry.insert(0, f"{video_length // 3600:02}:{(video_length % 3600) // 60:02}:{video_length % 60:02}")

                resolutions = [i.resolution for i in video.streams.filter(adaptive=True, file_extension='mp4')]
                key = resolutions
                resolutions = list(set(resolutions))
                resolutions.sort(key=key.index)
                video_resolution['values'] = resolutions
                showinfo(title='Search Complete', message='Check the Combobox for the available video resolutions')
            except:
                showerror(title='Error', message='An error occurred while searching for video resolutions!')

def get_best_audio_stream(video):
    """
    先找 256 kbps AAC(itag 141)；若沒有就找 160 kbps Opus(itag 251)；
    都沒有再 fallback 到 abr 最高的音訊串流
    """
    stream = video.streams.get_by_itag(141)        # 256 kbps AAC
    if stream:
        return stream
    stream = video.streams.get_by_itag(251)        # 160 kbps Opus
    if stream:
        return stream
    # 仍找不到就抓 abr 最大的那條
    return (video.streams
                .filter(only_audio=True)
                .order_by('abr').desc()
                .first())
    
def getTheBestResolution(video):
    """
    回傳目前影片可下載的最高解析度（ex. '4320p'、'2160p'、'1440p'…）
    """
    best = (video.streams
                .filter(adaptive=True, only_video=True, file_extension='mp4')
                .order_by('resolution')       # 由小→大
       把「抓音訊」的三個地方換         .desc()                        # 反轉成由大→小
                .first())                      # 取最高
    return best.resolution if best else None

def sanitize_filename(filename):
    # 1) 替換 Windows 不允許的字元
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 2) 避免控制字元或非可見字元
    filename = re.sub(r'[\x00-\x1f\x80-\x9f]', '', filename)
    return filename

def generate_new_filename(filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    new_filename = f"{base}({counter}){ext}"
    while os.path.exists(new_filename):
        counter += 1
        new_filename = f"{base} ({counter}){ext}"
    return new_filename

def get_nearest_keyframe_before(file_path, timestamp):
    command = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'frame=pts_time,pict_type',
        '-of', 'csv=p=0', '-read_intervals', f"{timestamp}%+10", file_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    keyframes = [line.split(',')[0] for line in result.stdout.splitlines() if 'I' in line]
    if keyframes:
        return keyframes[0]
    return None
def get_nearest_keyframe_after(file_path, timestamp):
    command = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'frame=pts_time,pict_type',
        '-of', 'csv=p=0', '-read_intervals', f"{timestamp}%+10", file_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    keyframes = [line.split(',')[0] for line in result.stdout.splitlines() if 'I' in line]
    if keyframes:
        if len(keyframes) > 1:
            return keyframes[1]
        else:
            return keyframes[0]
    return None

def time_to_seconds(time_str):
    h, m, s = [float(part) for part in time_str.split(':')]
    return h * 3600 + m * 60 + s    
    
def seconds_to_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:06.3f}"

def get_video_length(file_path):
    command = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    if result.returncode != 0:
        raise RuntimeError(f"Error getting video length: {result.stderr}")
    return float(result.stdout.strip())

def update_progress_bar(process, total_duration, progress_bar, progress_label, window):
    for line in process.stderr:
        if "time=" in line:
            time_split = line.split("time=")
            if len(time_split) > 1:
                time_str = time_split[1].split(" ")[0]
                time_parts = time_str.split(':')
                if len(time_parts) == 3:
                    try:
                        time_in_seconds = (int(time_parts[0]) * 3600) + (int(time_parts[1]) * 60) + float(time_parts[2])
                        percentage_completed = round((time_in_seconds / total_duration) * 100)
                        if percentage_completed > 100:
                            percentage_completed = 100
                        progress_bar['value'] = percentage_completed
                        update_progress_label(f'FFmpeg Processing: {percentage_completed}%', progress_label, window)
                        window.update()
                    except ValueError:
                        continue

def download_video(url_entry, video_resolution, download_option, is_playlist_var, save_path_var, process_option, start_time_entry, end_time_entry, progress_bar, progress_label, window):   
    try:
        video_link = url_entry.get()
        resolution_or_bitrate = video_resolution.get()
        download_type = download_option.get()  # 獲取當前所選的選項
        is_playlist = is_playlist_var.get()
        save_path = save_path_var.get()
        process_type = process_option.get()
        start_time = start_time_entry.get()
        end_time = end_time_entry.get()

        if resolution_or_bitrate == '' and video_link == '':
            showerror(title='Error', message='Please enter both the video URL and resolution/bitrate!!')
        elif resolution_or_bitrate == '' and download_type == 'video':
            showerror(title='Error', message='Please select a video resolution or audio bitrate!!')
        elif resolution_or_bitrate == 'None' and download_type == 'video':
            showerror(title='Error', message='None is an invalid video resolution or audio bitrate!!\nPlease select a valid option')
        elif not save_path:
            showerror(title='Error', message='Please select a save location!')
        elif process_type != 'none' and not(is_valid_time_format(start_time) and is_valid_time_format(end_time)) and not is_playlist:
            showerror(title='Error', message='Please enter both start and end times for the selected processing option! (Format "hh:mm:ss")')
        else:
            def on_progress(stream, chunk, bytes_remaining):
                        total_size = stream.filesize
                        bytes_downloaded = total_size - bytes_remaining
                        percentage_completed = round(bytes_downloaded / total_size * 100)
                        progress_bar['value'] = percentage_completed
                        update_progress_label(str(percentage_completed) + '%, File size:' + f"{total_size / (1024*1024):.2f} MB", progress_label, window)
                        window.update()
            ### Download Playlist
            if is_playlist:
                error_count = 0
                success_count = 0
                playlist = Playlist(video_link)
                for yt_video in playlist.videos:
                    try:
                        video = YouTube(yt_video.watch_url, on_progress_callback=on_progress)

                        if download_type == 'video':  # 當前選項為視頻下載
                            video_stream = video.streams.filter(res=getTheBestResolution(video), adaptive=True, file_extension='mp4').first()
                            audio_stream = get_best_audio_stream(video)

                            video_path = video_stream.download(filename='video.mp4')
                            audio_path = audio_stream.download(filename='audio.mp4')

                            video_title = sanitize_filename(video.title)  # 獲取影片標題並替換空格
                            output_path = os.path.join(save_path, f'{video_title}.mp4' if download_type == 'video' else f'{video_title}.mp3')
                            if os.path.exists(output_path):
                                output_path = generate_new_filename(output_path)
                            ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe')  # 指定 ffmpeg 的完整路徑

                            command = [
                                ffmpeg_path, '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', output_path
                            ]
                            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                            update_progress_bar(process, video.length, progress_bar, progress_label, window)

                            process.wait()
                            
                            if process.returncode != 0:
                                error_count += 1
                            else:
                                success_count += 1
                        else:  # 當前選項為音頻下載
                            audio_stream = get_best_audio_stream(video)
                            audio_path = audio_stream.download(filename='audio.mp4')
                            
                            video_title = sanitize_filename(video.title)  # 獲取影片標題並替換空格
                            output_path = os.path.join(save_path, f'{video_title}.mp3')
                            if os.path.exists(output_path):
                                output_path = generate_new_filename(output_path)
                            ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe')  # 指定 ffmpeg 的完整路徑
                            
                            command = [
                                    ffmpeg_path, '-i', audio_path, '-q:a', '0', '-map', 'a', output_path
                                ]
                            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                            update_progress_bar(process, video.length, progress_bar, progress_label, window)
                            process.wait()
                                
                            if process.returncode != 0:
                                error_count += 1
                            else:
                                success_count += 1
                    except Exception as e:
                        error_count += 1

                showinfo(title='Download Complete', message=f'Success: {success_count}, Failed: {error_count}')
            ### Download one Video or Audio
            else:
                try:
                    video = YouTube(video_link, on_progress_callback=on_progress)
                    
                    if download_type == 'video':  # 當前選項為視頻下載
                        video_stream = video.streams.filter(res=resolution_or_bitrate, adaptive=True, file_extension='mp4').first()
                        audio_stream = get_best_audio_stream(video)

                        video_path = video_stream.download(filename='video.mp4')
                        audio_path = audio_stream.download(filename='audio.mp4')

                        video_title = sanitize_filename(video.title)  # 獲取影片標題並替換空格
                        output_path = os.path.join(save_path, f'{video_title}.mp4' if download_type == 'video' else f'{video_title}.mp3')
                        if os.path.exists(output_path):
                            output_path = generate_new_filename(output_path)
                        ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe')  # 指定 ffmpeg 的完整路徑

                        # 判断处理选项
                        if process_type == 'none':
                            command = [
                                ffmpeg_path, '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', output_path
                            ]
                            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
                            update_progress_bar(process, video.length, progress_bar, progress_label, window)

                            stdout_data, stderr_data = process.communicate()  # 一次性讀完輸出
                            
                            if process.returncode == 0:
                                showinfo(title='Download Complete', message='Download completed successfully.')
                            else:
                                print(f"FFmpeg Return Code: {process.returncode}")
                                print(stderr_data)
                                showerror(title='FFmpeg Error', message=f'Error processing media:\n{stderr_data}')
                        elif process_type == 'quick':
                            start_keyframe = get_nearest_keyframe_before(video_path, start_time)
                            end_keyframe = get_nearest_keyframe_after(video_path, end_time)
                            if start_keyframe and end_keyframe:
                                temp_output = 'temp.mp4'
                                # 影音結合
                                command = [
                                    ffmpeg_path, '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', temp_output
                                ]
                                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                                update_progress_bar(process, video.length, progress_bar, progress_label, window)

                                process.wait()
                                if process.returncode != 0:
                                    showerror(title='FFmpeg Error', message=f'Error processing media: {process.stderr}')
                                    return
                                # 快速剪輯片段
                                command = [
                                    ffmpeg_path, '-ss', start_keyframe, '-i', temp_output, '-to', end_keyframe, '-c', 'copy', output_path
                                ]
                                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                                update_progress_bar(process, get_video_length(temp_output), progress_bar, progress_label, window)

                                process.wait()
                                if process.returncode != 0:
                                    showerror(title='FFmpeg Error', message=f'Error processing media: {process.stderr}')
                                    return
                            if process.returncode == 0:
                                showinfo(title='Download Complete', message='Download completed successfully.')
                            else:
                                showerror(title='FFmpeg Error', message=f'Error processing media: {process.stderr.read()}')
                        elif process_type == 'detailed':
                            start_keyframe = get_nearest_keyframe_before(video_path, start_time) # type 'second'
                            end_keyframe = get_nearest_keyframe_after(video_path, end_time) # type 'second'
                            if start_keyframe and end_keyframe:
                                temp_output = 'temp.mp4'
                                # 影音結合
                                command = [
                                    ffmpeg_path, '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', temp_output
                                ]
                                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                                update_progress_bar(process, video.length, progress_bar, progress_label, window)

                                process.wait()
                                if process.returncode != 0:
                                    showerror(title='FFmpeg Error', message=f'Error processing media: {process.stderr}')
                                    return
                                
                                # 快速剪輯片段
                                tmp_output = 'tmp.mp4'
                                command = [
                                    ffmpeg_path, '-ss', start_keyframe, '-i', temp_output, '-to', end_keyframe, '-c', 'copy', tmp_output
                                ]
                                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                                update_progress_bar(process, get_video_length(temp_output), progress_bar, progress_label, window)

                                process.wait()
                                if process.returncode != 0:
                                    showerror(title='FFmpeg Error', message=f'Error processing media: {process.stderr}')
                                    return
                                
                                # 詳細剪輯片段
                                start_seconds = time_to_seconds(start_time)
                                end_seconds = time_to_seconds(end_time)
                                start_offset = start_seconds - float(start_keyframe)
                                end_duration = end_seconds - start_seconds
                                start_offset_time = seconds_to_time(start_offset)
                                end_duration_time = seconds_to_time(end_duration)

                                command = [
                                    ffmpeg_path, '-ss', start_offset_time, '-i', tmp_output, '-to', end_duration_time, '-c:v', 'libx264', '-c:a', 'aac', output_path
                                ]

                                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                                update_progress_bar(process, video.length, progress_bar, progress_label, window)

                                process.wait()
                                
                                if process.returncode == 0:
                                    showinfo(title='Download Complete', message='Download completed successfully.')
                                else:
                                    showerror(title='FFmpeg Error', message=f'Error processing media: {process.stderr.read()}')

                    else:  # 當前選項為音頻下載
                        audio_stream = get_best_audio_stream(video)
                        audio_path = audio_stream.download(filename='audio.mp4')
                        
                        video_title = sanitize_filename(video.title)  # 獲取影片標題並替換空格
                        output_path = os.path.join(save_path, f'{video_title}.mp3')
                        if os.path.exists(output_path):
                            output_path = generate_new_filename(output_path)
                        ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe')  # 指定 ffmpeg 的完整路徑
                        
                        if process_type == 'none':
                            command = [
                                ffmpeg_path, '-i', audio_path, '-q:a', '0', '-map', 'a', output_path
                            ]
                            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                            update_progress_bar(process, video.length, progress_bar, progress_label, window)
                            process.wait()
                            
                            if process.returncode == 0:
                                showinfo(title='Download Complete', message='Download completed successfully.')
                            else:
                                print(process.stderr.read())
                                showerror(title='FFmpeg Error', message=f'Error processing media: {process.stderr.read()}')

                        else:
                            # 詳細剪輯片段
                            start_seconds = time_to_seconds(start_time)
                            end_seconds = time_to_seconds(end_time)
                            end_duration = end_seconds - start_seconds
                            end_duration_time = seconds_to_time(end_duration)

                            command = [
                                ffmpeg_path, '-ss', start_time, '-i', audio_path, '-t', end_duration_time, '-c:a', 'libmp3lame', '-b:a', '320k', output_path
                                ]
                            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                            update_progress_bar(process, video.length, progress_bar, progress_label, window)
                            process.wait()

                            if process.returncode == 0:
                                showinfo(title='Download Complete', message='Download completed successfully.')
                            else:
                                showerror(title='FFmpeg Error', message=f'Error processing media: {process.stderr.read()}')
                        

                except Exception as e:
                    showerror(title='Download Error', message=f'Failed to download video for this resolution: {e}')
                    update_progress_label('', progress_label, window)
                    progress_bar['value'] = 0

            update_progress_label('', progress_label, window)
            progress_bar['value'] = 0

            # Clean up temporary files
            if os.path.exists('audio.mp4'):
                os.remove('audio.mp4')
            if os.path.exists('video.mp4'):
                os.remove('video.mp4')
            if os.path.exists('temp.mp4'):
                os.remove('temp.mp4')
            if os.path.exists('tmp.mp4'):
                os.remove('tmp.mp4')

    except Exception as e:
        showerror(title='Download Error', message=f'An error occurred while trying to download the video: {e}')
        update_progress_label('', progress_label, window)
        progress_bar['value'] = 0
