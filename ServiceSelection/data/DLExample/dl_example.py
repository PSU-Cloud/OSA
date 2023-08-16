from pyspark import SparkContext, SparkConf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Activation
from tensorflow.keras.optimizers import SGD
from elephas.utils.rdd_utils import to_simple_rdd
from elephas.spark_model import SparkModel
from keras.datasets import mnist
from keras.models import Sequential, load_model
from keras.layers.core import Dense, Dropout, Activation
from keras.utils import np_utils

# Spark Parameters
MASTER_URL = '<insert master Spark Master URL>'


(x_train, y_train), (x_test, y_test) = mnist.load_data()

# building the input vector from the 28x28 pixels
x_train = x_train.reshape(60000, 784)
x_test = x_test.reshape(10000, 784)
x_train = x_train.astype('float32')
x_test = x_test.astype('float32')
# normalizing the data to help with the training
x_train /= 255
x_test /= 255

n_classes = 10
y_train = np_utils.to_categorical(y_train, n_classes)
y_test = np_utils.to_categorical(y_test, n_classes)

conf = SparkConf().setAppName('Elephas_App').setMaster(MASTER_URL)
sc = SparkContext(conf=conf)


model = Sequential()
model.add(Dense(512, input_shape=(784,)))
model.add(Activation('relu'))
model.add(Dropout(0.2))
model.add(Dense(512))
model.add(Activation('relu'))
model.add(Dropout(0.2))
model.add(Dense(10))
model.add(Activation('softmax'))
model.compile(loss='categorical_crossentropy', metrics=['accuracy'], optimizer='adam')

rdd = to_simple_rdd (sc, x_train, y_train)


spark_model = SparkModel(model, frequency='epoch', mode='asynchronous')
spark_model.fit(rdd, epochs=20, batch_size=32, verbose=0, validation_split=0.1)

exit()