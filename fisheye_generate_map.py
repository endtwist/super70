##
# In this script, we pre-generate the maps for fisheye undistortion
# based on our calibration constants we generated during training.
# The output is a pkl file that stores all of the remap data, which
# we can then load and use with cv2.remap on any images.
##

import cv2
import numpy as np
import pickle

# Calibration constants
DIM = (1440, 1080)
K = np.array([
    [1016.5369147826859, 0.0, 688.3081573170399],
    [0.0, 1014.5544799931812, 548.3455661473197],
    [0.0, 0.0, 1.0]
])
D = np.array([
    [-0.10197058195675843],
    [-0.052101191887192366],
    [0.06800048604354084],
    [-0.04464054041611462]
])

remap = {}


def undistort(dim1=None, balance=0.0, dim2=None, dim3=None):
    assert dim1[0]/dim1[1] == DIM[0]/DIM[1], \
        'Image to undistort needs to have same aspect ' + \
        'ratio as the ones used in calibration'
    if not dim2:
        dim2 = dim1
    if not dim3:
        dim3 = dim1

    # The values of K is to scale with image dimension.
    scaled_K = K * dim1[0] / DIM[0]
    scaled_K[2][2] = 1.0  # Except that K[2][2] is always 1.0

    # This is how scaled_K, dim2 and balance are used to determine the final
    # K used to un-distort image. OpenCV document failed to make this clear!
    new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
        scaled_K, D, dim2, np.eye(3), balance=balance)
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
        scaled_K, D, np.eye(3), new_K, dim3, cv2.CV_16SC2)

    remap[dim1] = {'map1': map1, 'map2': map2}


if __name__ == '__main__':
    undistort((320, 240), 0, (310, 233), (320, 240))
    undistort((640, 480), 0, (620, 465), (640, 480))
    undistort((1440, 1080), 0, (1440, 1080), (1440, 1080))
    undistort((3264, 2448), 0, (3264, 2448), (3264, 2448))

    output = open('remap.pkl', 'wb')
    pickle.dump(remap, output)
    output.close()
