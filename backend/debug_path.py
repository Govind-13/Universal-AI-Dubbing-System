
import os
import subprocess
import imageio_ffmpeg

# Setup Path same as service
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
ffmpeg_dir = os.path.dirname(ffmpeg_exe)
os.environ["PATH"] += os.pathsep + ffmpeg_dir

print(f"Directory added to PATH: {ffmpeg_dir}")
print(f"Executable is at: {ffmpeg_exe}")

# Check if 'ffmpeg' is now found
try:
    # Try running 'ffmpeg' as a command. 
    # Note: imageio provided binary might have a version suffix like ffmpeg-win64...exe
    # So 'ffmpeg' command might NOT work unless we rename it or the library handles it.
    print("Attempting to run 'ffmpeg -version'...")
    subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("Success: 'ffmpeg' command found!")
except FileNotFoundError:
    print("Failure: 'ffmpeg' command NOT found.")
except Exception as e:
    print(f"Error: {e}")

# Check actual binary name
print("Files in ffmpeg dir:")
print(os.listdir(ffmpeg_dir))
