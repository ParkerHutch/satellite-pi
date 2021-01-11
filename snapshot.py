from picamera import PiCamera
import subprocess
from time import sleep #TODO do I need this?
from typing import Dict, List
import os

""" 
    fswebcam arguments for image capture and processing
"""
capture_args = [
    '--resolution', '1280x720',
    #'--palette', 'JPEG',
    '--frames', '10'#,'--skip', '2'
]
processing_args = [
    '--banner-colour', '#FF0000', 
    '--font', 'sans:20',
    '--no-shadow',
    '--no-subtitle', 
    '--no-info']
# Whether to include the processing arguments when taking a photo with fswebcam
include_processing: bool = True 

# TODO use -palette option with fswebcam to take jpeg pictures
# TODO experiment with fswebcam flags for better pictures
camera = None
try:
    camera = PiCamera() # Make sure to close this on program end
except:
    print('no official Raspberry Pi camera connected')


def find_devices(search_range: int = 10) -> Dict[str, int]:
    """Return a dictionary of device filepaths as keys and the corresponding 
    number of cameras as values. Only devices that have 1 or more cameras are
    stored. If the PiCamera is connected, it will not be included in this list.

    Args:
        search_range (int, optional): The number of /dev/video{number} devices
        to check. Defaults to 10.

    Returns:
        dict[str, int]: A dictionary where each key is a device and each key's 
        corresponding value is the number of cameras associated with the 
        device.
    """

    camera_devices = {}
    for i in range(search_range):
        device_cameras = get_num_cameras(i)
        if device_cameras > 0:
            camera_devices[f'/dev/video{i}'] = device_cameras
    
    return camera_devices

def get_num_cameras(mount_num: int) -> int:
    """Get the number of cameras associated with the given video device. To 
    find the number of cameras, this function calls fswebcam with the
    --list-inputs flag on the /dev/video{mount_num} device and parses the output
    to find the last input's associated number. For a mount with one camera, the
    parsed output will be '0:Camera 1'. This function interprets the number
    found before the last colon to as the largest camera index. It is assumed
    that there is a valid camera on this mount for every integer value between
    this index and 0, and including 0.

    Args:
        mount_num (int): the postfix to the /dev/video path to check for 
        cameras on

    Returns:
        int: The number of valid cameras connected to the mount 
        /dev/video{mount_num}.
    """

    # Run a command to check the device's inputs and capture the output
    cmd_output = subprocess.check_output(
        [
            'script', '-q', '-c', 
            f'(fswebcam --list-inputs -d /dev/video{mount_num})', 
            '/dev/null'
        ], 
        text=True
    )
    error_messages = [
        'Unable to query input 0.', 
        'No such file or directory', 
        'Message from syslogd@raspberrypi'
    ]
    if any(message in cmd_output for message in error_messages):
        return 0
    else:
        start = 'Available inputs:'
        end = 'No input was specified'
        inputs_found = (cmd_output.split(start)[1]).split(end)[0]
        last_colon_index = inputs_found.rfind(':')
        largest_device_index = int(
            inputs_found[last_colon_index - 1: last_colon_index])
        return largest_device_index + 1

def get_fswebcam_capture_args(device: str, image_file_path:str) -> List[str]:
    """Generates an array of arguments to add to the 'fswebcam' command to take 
    a picture on the given device and store it in the file given by 
    image_file_path. The capture_args array is used to supply arguments 
    associated with image capture, and the processing_args array is used,
    if include_processing is True, to process the image after it is taken.  

    Args:
        device (str): The name of the device to use to take a picture, usually
        begins with /dev/video.
        image_file_path (str): The path to the file to store the image in.

    Returns:
        List[str]: a list of arguments to use in conjuction with the fswebcam
        command.
    """
    args = ['fswebcam', '-q', '-d', device]
    args.extend(capture_args)
    if include_processing:
        args.extend(processing_args)
        args.extend(['--title', f'DEVICE: {device}']) 
    else:
        args.extend(['--no-banner'])
    args.extend([image_file_path + '.jpg'])
    return args

def take_fswebcam_picture(device: str, log_file_path: str, 
                            image_file_path: str):
    """Uses the 'fswebcam' command to take a picture using the given device, 
    storing the image in the given image file path and appending the terminal
    output to the log file given by the log file path.

    Args:
        device (str): The device to use to take a picture. Usually begins with
        /dev/video.
        log_file_path (str): The path to the file where command line output 
        should be appended.
        image_file_path (str): The output image's file path and name
    """

    f = open(log_file_path, 'a')
    f.write(f'Attempting to take a picture on the {device} device\n')
    f.flush()
    subprocess.run(get_fswebcam_capture_args(device, image_file_path), stdout=f, stderr=f)

    f.write('DONE\n')
    f.flush()
    f.close()

# TODO add array of file extensions to remove
def prepare_directory(images_directory_path: str): 
    """Sets up the directory with given path so that it can hold incoming
    images. If the folder exists, any file with a image extension (see
    img_extensions array) or 'image' prefix is removed. If the folder doesn't
    exist, it is created. If the given path specifies a file, a warning is
    raised.

    Args:
        images_directory_path (str): The path to the folder that should be 
        prepared to hold images
    """

    # Files with these extensions will be removed
    img_extensions = ['.jpg', '.png']
    if os.path.isdir(images_directory_path):
        files = [ 
            f for f in os.listdir(images_directory_path) 
                if f.startswith('image') or f.endswith(tuple(img_extensions)) 
        ]
        for f in files:
            os.remove(os.path.join(images_directory_path, f))
    elif not os.path.exists(images_directory_path):
        os.makedirs(images_directory_path)
    else:
        print('Error: images directory is actually a file.') # TODO raise exception
    
def take_picture(camera_device: str = 'all', images_directory: str = "./images/"):
    """Take a picture using the given device, or on all connected devices, and
    store the output in the given directory.

    Args:
        camera_device (str, optional): The device to use to take pictures. Defaults to
        'all'.
        images_directory (str, optional): The relative filepath to store
        output images in. Defaults to "./images/".
    """

    prepare_directory(images_directory)

    if camera_device == 'picamera':
        camera.capture(images_directory + 'image.jpg')
    elif camera_device == 'all':
        # Take a picture on all connected USB cameras
        
        picture_num = 0

        # Take a picture on the PiCamera
        if camera is not None:
            camera.capture(images_directory + f'image{picture_num}.jpg')
            picture_num += 1

        # Clear the camera_log.txt file if it exists
        log_file_path = './camera_log.txt'
        open(log_file_path, 'w').close()

        for device_path, cameras in find_devices().items():
            for _ in range(cameras):
                take_fswebcam_picture(
                    device_path, 
                    log_file_path,
                    images_directory + f'image{str(picture_num)}'
                )
                picture_num += 1
    elif camera_device.startswith('/dev/video'):
        take_fswebcam_picture(camera_device, 
            images_directory + 'image.jpg')
    else:
        print(f'device {camera_device} is not supported')

def stop():
    """Close the PiCamera if it was initialized.
    """
    if camera is not None:
        camera.close()

if __name__ == '__main__':
    print('Clearing directory')
    prepare_directory('./images/')
    print('Cameras found:')
    print(find_devices())
    stop()