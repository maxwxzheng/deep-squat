import keras
from keras.models import Model, Sequential
from keras.layers import Dense, Dropout, Flatten
from keras.layers import Conv2D, MaxPooling2D
from keras.utils import to_categorical
from keras import backend as K
from keras import applications
from keras.callbacks import CSVLogger
import re
import cv2
import numpy as np
import os
import yaml
import matplotlib as mpl
mpl.use('TkAgg')
import matplotlib.pyplot as plt

import constants
from utils import Utils

class KerasModel():

  def run_all_experiments(overwrite=False):
    configs = yaml.load(open('experiments/configs.yml'))
    existing_result_files = os.listdir('experiments')
    for experiment_id in configs.keys():
      result_file_name_prefix = experiment_id
      print((result_file_name_prefix in existing_result_files) and not overwrite)
      if (result_file_name_prefix in existing_result_files) and not overwrite:
        continue

      config = configs[experiment_id]
      KerasModel.run(epochs=config['epochs'],
                     base_model=config['base_model'],
                     base_model_layer=config['base_model_layer'],
                     learning_rate=config['learning_rate'],
                     result_file_name_prefix="experiments/{}".format(result_file_name_prefix))

  def run(epochs=100,
          batch_size=-1,
          base_model=None,
          base_model_layer=0,
          learning_rate=0.0001,
          result_file_name_prefix='log'):
    train_images, train_labels = KerasModel.load_images_and_labels(constants.FULL_SQUAT_TRAIN_FOLDER)
    dev_images, dev_labels = KerasModel.load_images_and_labels(constants.FULL_SQUAT_DEV_FOLDER)
    input_shape = (constants.IMAGE_HEIGHT, constants.IMAGE_WIDTH, 3)

    train_labels = to_categorical(train_labels)
    dev_labels = to_categorical(dev_labels)

    if base_model == 'VGG16':
      base_model = applications.VGG16(weights = "imagenet", include_top=False, input_shape = (constants.IMAGE_HEIGHT, constants.IMAGE_WIDTH, 3))
    elif base_model == 'ResNet50':
      base_model = applications.ResNet50(weights = "imagenet", include_top=False, input_shape = (constants.IMAGE_HEIGHT, constants.IMAGE_WIDTH, 3))
    elif base_model == 'Xception':
      base_model = applications.Xception(weights = "imagenet", include_top=False, input_shape = (constants.IMAGE_HEIGHT, constants.IMAGE_WIDTH, 3))
    else:
      print("Using custom model")
      if base_model_layer != -1 and base_model_layer != 0:
        raise 'Custom model must use base_model_layer -1 or 0'
      base_model = KerasModel.custom_model()

    if base_model_layer == -1:
      x = base_model.layers[-1].output
    else:
      for layer in base_model.layers:
        layer.trainable = False
      x = base_model.layers[base_model_layer].output

    x = Flatten()(x)
    x = Dense(128, activation="relu")(x)
    x = Dropout(0.5)(x)
    predictions = Dense(2, activation='sigmoid')(x)
    model_final = Model(input=base_model.input, output=predictions)
    print(model_final.layers)

    model_final.compile(loss = "binary_crossentropy",
                        optimizer = keras.optimizers.Adam(lr=learning_rate),
                        metrics=["accuracy"])

    if batch_size == -1:
      batch_size = len(train_images)

    # Save the result to csv file.
    csv_file_name = result_file_name_prefix + '.csv'
    csv_logger = CSVLogger(csv_file_name, separator=';')
    model_log = model_final.fit(train_images, train_labels,
                                batch_size=batch_size,
                                epochs=epochs,
                                verbose=1,
                                validation_data=(dev_images, dev_labels),
                                callbacks=[csv_logger])

    KerasModel.save_plot_history(model_log, result_file_name_prefix)
    KerasModel.save_model(model_final, result_file_name_prefix)
    KerasModel.save_test_result(model_final, result_file_name_prefix)

  def save_plot_history(model_log, result_file_name_prefix):
    fig = plt.figure()
    
    plt.subplot(2,1,1)
    plt.plot(model_log.history['acc'])
    plt.plot(model_log.history['val_acc'])
    plt.title('model accuracy')
    plt.ylabel('accuracy')
    plt.xlabel('epoch')
    plt.legend(['train', 'dev'], loc='lower right')

    plt.subplot(2,1,2)
    plt.plot(model_log.history['loss'])
    plt.plot(model_log.history['val_loss'])
    plt.title('model loss')
    plt.ylabel('loss')
    plt.xlabel('epoch')
    plt.legend(['train', 'dev'], loc='upper right')
    plt.tight_layout()

    plt_file_name = result_file_name_prefix + '.png'
    plt.savefig(plt_file_name)

  def save_model(model, result_file_name_prefix):
    model_file_name = result_file_name_prefix + '.json'
    model_digit_json = model.to_json()
    with open(model_file_name, 'w') as json_file:
      json_file.write(model_digit_json)
    
    model_weight_file_name = result_file_name_prefix + '.h5'
    model.save_weights(model_weight_file_name)

  def save_test_result(model, result_file_name_prefix):
    test_images, test_labels = KerasModel.load_images_and_labels(constants.FULL_SQUAT_TEST_FOLDER)
    test_labels = to_categorical(test_labels)

    score = model.evaluate(test_images, test_labels, verbose=0)
    csv_file_name = result_file_name_prefix + '.csv'
    with open(csv_file_name,'a') as fd:
      fd.write(';'.join(['test', str(score[1]), str(score[0])]))

  def custom_model():
    model = Sequential()
    input_shape = (constants.IMAGE_HEIGHT, constants.IMAGE_WIDTH, 3)
    model.add(Conv2D(32, kernel_size=(3, 3), activation='relu', input_shape=input_shape))
    model.add(Conv2D(64, (3, 3), activation='relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))
    return model

  def extract_labels(file_names):
    labels = []
    for file_name in file_names:
      match = re.match(".*\.mp4_\d+_(\d)_\d+.*\.jpg", file_name)
      labels.append(int(match[1]))
    return labels

  def load_images_and_labels(folder):
    image_names = Utils.get_image_names(folder)

    # Load the images into an array
    images = []
    for image_name in image_names:
      images.append(cv2.imread("{}/{}".format(folder, image_name)))

    # Extract the labels from the image names
    labels = KerasModel.extract_labels(image_names)

    return np.array(images), np.array(labels)