__author__ = 'yoyomyo'
import os,sys,math,pdb
import numpy as np
import cv2
from itertools import combinations

class Chord:

    def __init__(self, pt1, pt2, pt1_prev, pt1_next, pt2_prev, pt2_next, cnt_centroid):
        # chord is a vector from pt1 to pt2
        self.chord = (pt2-pt1)[0]

        self.mid = (pt1+pt2)/2
        self.pt1 = pt1
        self.pt2 = pt2
        self.length = dist(pt1, pt2)
        self.pt1_normal_angle = self.get_normal(pt1, pt1_prev, pt1_next, cnt_centroid)
        self.pt2_normal_angle = self.get_normal(pt2, pt2_prev, pt2_next, cnt_centroid)
        self.orientation_angle = self.get_orientation(cnt_centroid)

    # make sure that normal is pointing towards the innder contour
    def get_normal(self, pt, prev, next, center):
        # a vector point from pt to the center of contour
        pt_center = (center-pt)[0]
        dx, dy = (next-prev)[0]
        #tangent = (next-prev)[0]
        # there are two normals
        # need to pick the one point to the center
        normal1 = (-dy,dx)
        normal2 = (dy,-dx)

        # dot product
        dp1 = dotproduct(normal1, pt_center)
        if dp1 >=0.0:
            return angle(normal1, pt_center)
        else:
            return angle(normal2, pt_center)

    def get_orientation(self,cnt_centroid):
        x, y = self.chord
        normal1 = (-y,x)
        normal2 = (y,-x)
        mid_center = (cnt_centroid - self.mid)[0]
        #return math.atan2(x, y)
        # dot product
        dp1 = dotproduct(mid_center, normal1)
        if dp1 > 0:
            return angle(normal1, mid_center)
        else:
            return angle(normal2, mid_center)

class ShapeDetector:

    SAMPLE_SIZE = 16

    MAX_IMG_DIM = 1000              # if width or height greater than 1000 pixels, processing image would be slow

    MORPH_DIM = (3,3)

    CONTOUR_THRESHOLD = 50          # if a contour does not contain more than 50 pixels,
                                    # then we are not interested in the contour
    RED = (0,0,255)
    GREEN = (0,255,0)
    BLUE = (255,0,0)
    YELLOW = (0,255,255)

    EPS = 0.0001                    # used to prevent the zero case when computing log

    # used to build chordiogram
    ANGLE_BINS_ONE = [x*math.pi for x in np.arange(0,0.5,0.03124999)]

    ANGLE_BINS_TWO = [x*math.pi for x in np.arange(0,1,0.124999)]

    LENGTH_BINS = [math.log(x) for x in [1., 6.28, 39.44, 247.67, 1555.38]]

    NUM_CLASS = 2

    NESTED_CONTOUR_DISTANCE = 10    #if a two contours are nested and their boundaries
                                    # are within 10px then remove the innner conotur

    def get_training_data(self, dir):
        for root, subdirs, files in os.walk(dir):
            for file in files:
                if os.path.splitext(file)[1].lower() in ('.jpg', '.jpeg', '.png'):
                    path_to_img = os.path.join(root,file)
                    self.get_training_data_from_img(path_to_img)

    # get shapes from image and store shape
    # information (chordiogram) in a file for training classifier
    def get_training_data_from_img(self, path_to_img):
        img = cv2.imread(path_to_img)
        color, bw = self.preprocess_image(img)
        self.get_training_samples(color, bw)

    # get shape features from img, put them into ,
    # and store relevant shape into
    def get_training_data_from_img2(self, img_name, img_class):
        img = cv2.imread('train/'+img_name)
        color, bw_img = self.preprocess_image(img)
        self.get_features(bw_img, img_class)

    def get_training_data2(self):
        for i in range(0,self.NUM_CLASS):
            img_name = str(i)+'.jpg'
            img_class = i
            self.get_training_data_from_img2(img_name, img_class)

    def preprocess_image(self, img):
        w,h,c = img.shape
        while w > self.MAX_IMG_DIM or h > self.MAX_IMG_DIM:
            img = cv2.pyrDown(img)
            w,h,c = img.shape
        # convert image to grayscale
        imgray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        # generate adaptive thresholding parameters
        thresh = cv2.adaptiveThreshold(imgray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,\
                                        cv2.THRESH_BINARY,21, 10)
        ret,thresh = cv2.threshold(thresh,127,255,0)
        # apply erosion and dilation, this is for trying to close gaps in a contour
        element1 = cv2.getStructuringElement(cv2.MORPH_RECT,self.MORPH_DIM)
        element2 = cv2.getStructuringElement(cv2.MORPH_RECT,self.MORPH_DIM)
        img2 = cv2.erode(thresh,element2)
        img3 = cv2.dilate(img2,element1)
        # use the complement of the dilated image
        img3 = 255-img3
        #self.show_image_in_window('preprocess', img3)
        return img,img3

    def train_classifier(self):
        samples = np.loadtxt('TrainingResponses/generalsamples.data',np.float32)
        responses = np.loadtxt('TrainingResponses/generalresponses.data',np.float32)
        responses = responses.reshape((responses.size,1))
        model = cv2.SVM()
        model.train(samples,responses)
        return model

    def show_image_in_window(self, win_name, img):
        cv2.imshow(win_name,img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    # parameter used in this function:
    def get_training_samples(self,color_img, bw_img):
        samples =  np.empty((0,self.SAMPLE_SIZE))
        responses = []
        keys = [48,49,50] # key responses are 0=circle, 1=rectangle, 2=triangle

        contours, hierarchy = cv2.findContours(bw_img,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        contours = self.filter_contours(contours)

        for cnt in contours:
            print len(cnt)
            x,y,w,h = cv2.boundingRect(cnt)
            cv2.rectangle(color_img,(x,y),(x+w,y+h),self.RED,2)

            # centroid = self.get_contour_centroid(cnt)
            chords = self.get_chords(cnt)
            chord_entries = [chord.orientation_angle for chord in chords]
            # for chord in chords:
            #     chord_entry = [math.log(chord.length+0.001),
            #                    chord.orientation_angle,
            #                    chord.pt1_normal_angle,
            #                    chord.pt2_normal_angle]
            #     #0print chord_entry
            #     chord_entries.append(chord_entry)
            # chordiogram = np.histogramdd(np.array(chord_entries), bins = np.array([self.LENGTH_BINS, self.ANGLE_BINS, self.ANGLE_BINS, self.ANGLE_BINS]))

            chordiogram = np.histogram(chord_entries, bins = self.ANGLE_BINS)

            # strech chordiogram to one dimensional
            chordiogram_1d = np.reshape(chordiogram[0], (1, self.SAMPLE_SIZE))
            chordiogram_1d = chordiogram_1d/float(len(chords))
            #pdb.set_trace()
            cv2.imshow('norm',color_img)
            key = cv2.waitKey(0)
            if key == 27:
                sys.exit()
            elif key in keys:
                responses.append(int(chr(key)))
                samples = np.append(samples, chordiogram_1d, 0)
            cv2.destroyAllWindows()

        responses = np.array(responses,np.float32)
        responses = responses.reshape((responses.size,1))
        print responses

        np.savetxt('TrainingResponses/tmp_samples.data',samples)
        np.savetxt('TrainingResponses/tmp_responses.data',responses)

    # parameter used in this function:
    def get_features(self, bw_img, img_class):
        samples = np.empty((0,self.SAMPLE_SIZE))

        contours, hierarchy = cv2.findContours(bw_img,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        contours = self.filter_contours(contours)
        print len(contours)
        for cnt in contours:
            features = self.get_feature_helper(cnt)
            samples = np.append(samples, features, 0)

        responses = [img_class]*len(samples)
        responses = np.array(responses,np.float32)
        responses = responses.reshape((responses.size,1))

        np.savetxt('TrainingResponses/tmp_samples.data',samples)
        np.savetxt('TrainingResponses/tmp_responses.data',responses)
        self.append_result_to_file()

    def get_feature_helper(self, cnt):
        chords = self.get_chords(cnt)
        features = []
        for chord in chords:
            l = chord.length
            o = chord.orientation_angle
            n1 = chord.pt1_normal_angle
            n2 = chord.pt2_normal_angle
            features.append([o])
        #chordiogram, edges = np.histogramdd(np.array(features),  bins = np.array([self.ANGLE_BINS_ONE, self.ANGLE_BINS_TWO, self.ANGLE_BINS_TWO]))
        chordiogram, edges = np.histogramdd(np.array(features),  bins = np.array([self.ANGLE_BINS_ONE]))
        # strech chordiogram to one dimensional
        # pdb.set_trace()

        chordiogram_1d = np.reshape(chordiogram, (1, self.SAMPLE_SIZE))
        chordiogram_1d = chordiogram_1d/float(len(chords))
        return chordiogram_1d

    # maybe use a better method
    def append_result_to_file(self):
        with open("TrainingResponses/generalresponses.data", "a") as f1:
            with open("TrainingResponses/tmp_responses.data", "r") as f2:
                f1.write(f2.read())

        with open("TrainingResponses/generalsamples.data", "a") as f3:
            with open("TrainingResponses/tmp_samples.data", "r") as f4:
                f3.write(f4.read())

    # given a contour
    # return a list of chords
    # each chord has pt1, pt2, normal at pt1, normal at pt2, length, chords orientation
    def get_chords(self, contour):

        num_points = len(contour)
        pairs = combinations(range(num_points), 2)
        centroid = self.get_contour_centroid(contour)
        chords = []
        for x,y in pairs:
            chord = Chord(pt1=contour[x],
                          pt2=contour[y],
                          pt1_prev= contour[(x-1)%num_points],     # if first or last pair,
                          pt1_next= contour[(x+1)%num_points],    # wrap around contour to find two nearest points
                          pt2_prev= contour[(y-1)%num_points],     # else shift the contour by 1
                          pt2_next= contour[(y+1)%num_points],    # to the left and 1 to the right
                          cnt_centroid = centroid)
            chords.append(chord)
        return chords


    def draw_chords(self, img, chord, cnt_centroid):
        NORMAL_FACTOR = 0.1
        p1 = chord.pt1[0]
        p2 = chord.pt2[0]
        mid = chord.midpoint[0]

        p1_normal = np.rint(chord.pt1_normal[0]*NORMAL_FACTOR)
        p2_normal = np.rint(chord.pt2_normal[0]*NORMAL_FACTOR)
        orientation = np.rint(chord.orientation*NORMAL_FACTOR, cnt_centroid)

        # test if the values are correct
        draw_line(img,p1,p1_normal.astype(int),self.RED)
        draw_line(img, p2, p2_normal.astype(int),self.GREEN)
        cv2.line(img, tuple(p1), tuple(p2), self.BLUE)

        draw_line(img, mid, orientation.astype(int), self.YELLOW)

    def get_contour_centroid(self, cnt):
        # compute the centroid of the contour to help compute chord normals and orientation
        M = cv2.moments(cnt)
        centroid_x = int(M['m10']/M['m00'])
        centroid_y = int(M['m01']/M['m00'])
        return np.array([centroid_x,centroid_y])

    def get_contour_extreme_points(self, cnt):
        leftmost = tuple(cnt[cnt[:,:,0].argmin()][0])
        rightmost = tuple(cnt[cnt[:,:,0].argmax()][0])
        topmost = tuple(cnt[cnt[:,:,1].argmin()][0])
        bottommost = tuple(cnt[cnt[:,:,1].argmax()][0])
        return [leftmost, rightmost, topmost, bottommost]

    def filter_contours(self, contours):
        contours = filter(lambda cnt: len(cnt) > self.CONTOUR_THRESHOLD, contours)
        contours = self.remove_nested_contours(contours)
        return contours

    def remove_nested_contours(self, contours):
        contour_table = {}
        for i, cnt in enumerate(contours):
            to_add = self.get_contour_extreme_points(cnt)
            if len(contour_table) == 0:
                contour_table[i] = to_add
            else:
                to_replace = i
                for k in contour_table:
                    flag = self.are_nested_contour(contour_table[k], to_add)
                    if flag == 1:
                        # former contour is larger, do not add
                        to_replace = -1
                    elif flag == 2:
                        # latter contour is larger, replace
                        to_replace = k

                if to_replace != -1:
                    contour_table[to_replace] = to_add

        indexes = contour_table.keys()
        return [contours[i] for i in indexes]

    # return 1 if extreme_points2 is nested within extreme_points1
    # return 2 if extreme_points1 is nested within extreme_points2
    # otherwise return 3
    def are_nested_contour(self, extreme_points1, extreme_points2):
        left1, right1, top1, bottom1 = extreme_points1
        left2, right2, top2, bottom2 = extreme_points2
        xl1, yl1 = left1
        xl2, yl2 = left2
        xr1, yr1 = right1
        xr2, yr2 = right2
        xt1, yt1 = top1
        xt2, yt2 = top2
        xb1, yb1 = bottom1
        xb2, yb2 = bottom2

        a = self.withinContourDistance(xl1, xl2)
        b = self.withinContourDistance(xr2, xr1)
        c = self.withinContourDistance(yt1, yt2)
        d = self.withinContourDistance(yb2, yb1)

        e = self.withinContourDistance(xl2, xl1)
        f = self.withinContourDistance(xr1, xr2)
        g = self.withinContourDistance(yt2, yt1)
        h = self.withinContourDistance(yb1, yb2)

        if e and f and g and h:
            return 1
        elif a and b and c and d:
            return 2

        return 3

    def withinContourDistance(self, p1, p2):
        return withinDistance(p1,p2,self.NESTED_CONTOUR_DISTANCE)

    # compute chordiogram for each contour, used in testing
    def get_contour_info(self, cnt):

        # centroid = self.get_contour_centroid(cnt)
        chords = self.get_chords(cnt)
        chord_entries = [chord.orientation_angle for chord in chords]

        # for chord in chords:
        #     chord_entry = [math.log(max(chord.length, self.EPS)),
        #                    chord.orientation_angle,
        #                    chord.pt1_normal_angle,
        #                    chord.pt2_normal_angle]
        #     chord_entries.append(chord_entry)
        # chordiogram = np.histogramdd(np.array(chord_entries), bins = np.array([self.LENGTH_BINS, self.ANGLE_BINS, self.ANGLE_BINS, self.ANGLE_BINS]))

        chordiogram = np.histogram(chord_entries, bins = self.ANGLE_BINS)
        # strech chordiogram to one dimensional
        chordiogram_1d = np.reshape(chordiogram[0], (1, self.SAMPLE_SIZE))
        chordiogram_1d = chordiogram_1d/float(len(chords))
        return chordiogram_1d

    # mark the shapes in img
    def test_classifier(self, path_to_img, svm):
        img = cv2.imread(path_to_img)
        color, bw = self.preprocess_image(img)
        contours, hierarchy = cv2.findContours(bw,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        contours = self.filter_contours(contours)
        for cnt in contours:
            [x,y,w,h] = cv2.boundingRect(cnt)
            chordiogram = self.get_feature_helper(cnt)
            #print chordiogram
            #pdb.set_trace()
            chordiogram = np.array(chordiogram,np.float32)
            shape_class = svm.predict(chordiogram)
            print shape_class
            options = {0 : self.RED,
                1 : self.GREEN,
                2 : self.BLUE
            }
            self.mark_shape(color, x,y,w,h,options[shape_class])

        self.show_image_in_window('PREDICTION', color)

    def mark_shape(self, img, x,y,w,h,color):
        cv2.rectangle(img,(x,y),(x+w,y+h),color,1)
# global helper functions
def midpoint(p1, p2):
    return (p1+p2)/2

def normalize(v):
    return v/np.linalg.norm(v)

def dist(p1,p2):
    return np.linalg.norm(p1-p2)

def draw_line(img, start, vec, color):
    end = tuple(start + vec)
    cv2.line(img, tuple(start), end, color)

def dotproduct(v1, v2):
  return sum((a*b) for a, b in zip(v1, v2))

def length(v):
  return math.sqrt(dotproduct(v, v))

def angle(v1, v2):
    cosine = dotproduct(v1, v2) / (length(v1) * length(v2)+0.0001)
    # print math.acos(cosine)/math.pi*180
    return math.acos(cosine)

def withinDistance(p1, p2, distance):
    return p1 >= p2 and p1-p2 <= distance

sd = ShapeDetector()
#sd.get_training_data2()
#sd.get_training_data_from_img('train/0.jpg')

svm = sd.train_classifier()
sd.test_classifier('test/7.jpg', svm)