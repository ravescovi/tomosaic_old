#!/usr/bin/env python
    display_min, display_max = limits
	# make phase retrieval subdirectories

            # load flats and darks
            # write downsampled data frame-by-frame
                print('\r    At frame {:d}'.format(frame), end='')
                temp = temp.reshape([1, temp.shape[0], temp.shape[1]])
                temp = tomopy.normalize(temp, flt[flats],drk[darks])
                temp = np.squeeze(temp)
            print(' ')
      

        ##this looks at the wrong level