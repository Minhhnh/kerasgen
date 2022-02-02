"""Tests for balanced_image_dataset."""

import tensorflow.compat.v2 as tf

import os
import shutil

import numpy as np
from tensorflow.python.keras import keras_parameterized
from tensorflow.python.keras.preprocessing import image as image_preproc
from kerasgen import balanced_image_dataset

try:
  import PIL  # pylint:disable=g-import-not-at-top
except ImportError:
  print('Please Install Pillow')
  PIL = None

class BalancedImageDatasetFromDirectoryTest(keras_parameterized.TestCase):

  def __init__(self, methodName="runTest"):
    super().__init__(methodName)

  def _get_images(self, count=16, color_mode='rgb'):
    width = height = 24
    imgs = []
    for _ in range(count):
      if color_mode == 'grayscale':
        img = np.random.randint(0, 256, size=(height, width, 1))
      elif color_mode == 'rgba':
        img = np.random.randint(0, 256, size=(height, width, 4))
      else:
        img = np.random.randint(0, 256, size=(height, width, 3))
      img = image_preproc.array_to_img(img)
      imgs.append(img)
    return imgs

  def _prepare_directory(self,
                         num_classes=2,
                         grayscale=False,
                         nested_dirs=False,
                         color_mode='rgb',
                         count=16):
    # Get a unique temp directory
    temp_dir = os.path.join(self.get_temp_dir(), str(np.random.randint(1e6)))
    os.mkdir(temp_dir)
    self.addCleanup(shutil.rmtree, temp_dir)

    # Generate paths to class subdirectories
    paths = []
    for class_index in range(num_classes):
      class_directory = 'class_%s' % (class_index,)
      if nested_dirs:
        class_paths = [
            class_directory, os.path.join(class_directory, 'subfolder_1'),
            os.path.join(class_directory, 'subfolder_2'), os.path.join(
                class_directory, 'subfolder_1', 'sub-subfolder')
        ]
      else:
        class_paths = [class_directory]
      for path in class_paths:
        os.mkdir(os.path.join(temp_dir, path))
      paths += class_paths

    # Save images to the paths
    i = 0
    for img in self._get_images(color_mode=color_mode, count=count):
      path = paths[i % len(paths)]
      if color_mode == 'rgb':
        ext = 'jpg'
      else:
        ext = 'png'
      filename = os.path.join(path, 'image_%s.%s' % (i, ext))
      img.save(os.path.join(temp_dir, filename))
      i += 1
    return temp_dir

  def test_balanced_image_dataset_from_directory_standalone(self):
    # Test retrieving images without labels from a directory and its subdirs.
    if PIL is None:
      return  # Skip test if PIL is not available.

    # Save a few extra images in the parent directory.
    directory = self._prepare_directory(count=7, num_classes=2)
    for i, img in enumerate(self._get_images(3)):
      filename = 'image_%s.jpg' % (i,)
      img.save(os.path.join(directory, filename))

    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=2, image_size=(18, 18), labels=None)
    batch = next(iter(dataset))
    # We return plain images
    self.assertEqual(batch.shape, (4, 18, 18, 3))
    self.assertEqual(batch.dtype.name, 'float32')
    # Count samples
    batch_count = 0
    sample_count = 0
    for batch in dataset:
      batch_count += 1
      sample_count += batch.shape[0]
    self.assertEqual(batch_count, 2)
    self.assertEqual(sample_count, 7)

  def test_balanced_image_dataset_from_directory_binary(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=2)
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), label_mode='int')
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (8, 18, 18, 3))
    self.assertEqual(batch[0].dtype.name, 'float32')
    self.assertEqual(batch[1].shape, (8,))
    self.assertEqual(batch[1].dtype.name, 'int32')

    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), label_mode='binary')
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (8, 18, 18, 3))
    self.assertEqual(batch[0].dtype.name, 'float32')
    self.assertEqual(batch[1].shape, (8, 1))
    self.assertEqual(batch[1].dtype.name, 'float32')

    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), label_mode='categorical')
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (8, 18, 18, 3))
    self.assertEqual(batch[0].dtype.name, 'float32')
    self.assertEqual(batch[1].shape, (8, 2))
    self.assertEqual(batch[1].dtype.name, 'float32')

  def test_static_shape_in_graph(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=2)
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), label_mode='int')
    test_case = self

    @tf.function
    def symbolic_fn(ds):
      for x, _ in ds.take(1):
        test_case.assertListEqual(x.shape.as_list(), [None, 18, 18, 3])

    symbolic_fn(dataset)

  def test_sample_count(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=4, count=15)
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), label_mode=None)
    sample_count = 0
    for batch in dataset:
      sample_count += batch.shape[0]
    self.assertEqual(sample_count, 15)

  def test_balanced_image_dataset_from_directory_multiclass(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=4, count=15)

    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), label_mode=None)
    batch = next(iter(dataset))
    self.assertEqual(batch.shape, (8, 18, 18, 3))

    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), label_mode=None)
    sample_count = 0
    iterator = iter(dataset)
    for batch in dataset:
      sample_count += next(iterator).shape[0]
    self.assertEqual(sample_count, 15)

    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), label_mode='int')
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (8, 18, 18, 3))
    self.assertEqual(batch[0].dtype.name, 'float32')
    self.assertEqual(batch[1].shape, (8,))
    self.assertEqual(batch[1].dtype.name, 'int32')

    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), label_mode='categorical')
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (8, 18, 18, 3))
    self.assertEqual(batch[0].dtype.name, 'float32')
    self.assertEqual(batch[1].shape, (8, 4))
    self.assertEqual(batch[1].dtype.name, 'float32')

  def test_balanced_image_dataset_from_directory_color_modes(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=4, color_mode='rgba')
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), color_mode='rgba')
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (8, 18, 18, 4))
    self.assertEqual(batch[0].dtype.name, 'float32')

    directory = self._prepare_directory(num_classes=4, color_mode='grayscale')
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), color_mode='grayscale')
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (8, 18, 18, 1))
    self.assertEqual(batch[0].dtype.name, 'float32')

  def test_balanced_image_dataset_from_directory_validation_split(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=2, count=50)
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=5, image_size=(18, 18),
        validation_split=0.2, subset='training', seed=1337)
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (10, 18, 18, 3))
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=5, image_size=(18, 18),
        validation_split=0.2, subset='validation', seed=1337)
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (10, 18, 18, 3))

  def test_balanced_image_dataset_from_directory_manual_labels(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=2, count=2)
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=1, image_size=(18, 18),
        labels=[0, 1], shuffle=False)
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertAllClose(batch[1], [0, 1])

  def test_balanced_image_dataset_from_directory_follow_links(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=2, count=16,
                                        nested_dirs=True)
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=4, image_size=(18, 18), 
        label_mode=None, follow_links=True)
    sample_count = 0
    for batch in dataset:
      sample_count += batch.shape[0]
    self.assertEqual(sample_count, 16)

  def test_balanced_image_dataset_from_directory_no_images(self):
    directory = self._prepare_directory(num_classes=2, count=0)
    with self.assertRaisesRegex(ValueError, 'No images found.'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(directory)

  def test_balanced_image_dataset_from_directory_crop_to_aspect_ratio(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=2, count=5)
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=2, num_images_per_class=2, image_size=(18, 18), 
        crop_to_aspect_ratio=True)
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (4, 18, 18, 3))

  def test_balanced_image_dataset_from_directory_safe_triplet(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=4, count=4)
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=4, num_images_per_class=2, image_size=(18, 18), 
        safe_triplet=True)
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (8, 18, 18, 3))

  def test_balanced_image_dataset_from_directory_samples_per_epoch(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=4, count=4)
    dataset = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=4, num_images_per_class=2, image_size=(18, 18), 
        safe_triplet=True, samples_per_epoch=800)
    batch = next(iter(dataset))
    self.assertLen(batch, 2)
    self.assertEqual(batch[0].shape, (8, 18, 18, 3))

  def test_balanced_image_dataset_from_directory_errors(self):
    if PIL is None:
      return  # Skip test if PIL is not available.

    directory = self._prepare_directory(num_classes=3, count=5)

    with self.assertRaisesRegex(ValueError, '`labels` argument should be'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, labels='other')

    with self.assertRaisesRegex(ValueError, '`label_mode` argument must be'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, label_mode='other')

    with self.assertRaisesRegex(ValueError, '`color_mode` must be one of'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, color_mode='other')

    with self.assertRaisesRegex(
        ValueError, 'only pass `class_names` if `labels="inferred"`'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, labels=[0, 0, 1, 1, 1],
          class_names=['class_0', 'class_1', 'class_2'])

    with self.assertRaisesRegex(
        ValueError,
        'Expected the lengths of `labels` to match the number of files'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, labels=[0, 0, 1, 1])

    with self.assertRaisesRegex(
        ValueError, '`class_names` passed did not match'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, class_names=['class_0', 'class_2'])

    with self.assertRaisesRegex(ValueError, 'there must be exactly 2'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, label_mode='binary')

    with self.assertRaisesRegex(ValueError,
                                '`validation_split` must be between 0 and 1'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, validation_split=2)

    with self.assertRaisesRegex(ValueError,
                                '`subset` must be either "training" or'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, validation_split=0.2, subset='other')

    with self.assertRaisesRegex(ValueError, '`validation_split` must be set'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, validation_split=0, subset='training')

    with self.assertRaisesRegex(ValueError, 'must provide a `seed`'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
          directory, validation_split=0.2, subset='training')

    with self.assertRaisesRegex(ValueError, '`samples_per_epoch` must be divisible by batch_size'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=4, num_images_per_class=2, image_size=(18, 18), 
        safe_triplet=True, samples_per_epoch=796)

    with self.assertRaisesRegex(ValueError, 'You can only pass `samples_per_epoch` if safe_triplet is True'):
      _ = balanced_image_dataset.balanced_image_dataset_from_directory(
        directory, num_classes_per_batch=4, num_images_per_class=2, image_size=(18, 18), 
        samples_per_epoch=796)

if __name__ == '__main__':
    Tester = BalancedImageDatasetFromDirectoryTest()
    Tester.test_balanced_image_dataset_from_directory_standalone()
    Tester.test_balanced_image_dataset_from_directory_binary()
    Tester.test_static_shape_in_graph()
    Tester.test_sample_count()
    Tester.test_balanced_image_dataset_from_directory_color_modes()
    Tester.test_balanced_image_dataset_from_directory_validation_split()
    Tester.test_balanced_image_dataset_from_directory_manual_labels()
    Tester.test_balanced_image_dataset_from_directory_follow_links()
    Tester.test_balanced_image_dataset_from_directory_no_images()
    Tester.test_balanced_image_dataset_from_directory_crop_to_aspect_ratio()
    Tester.test_balanced_image_dataset_from_directory_safe_triplet()
    Tester.test_balanced_image_dataset_from_directory_samples_per_epoch()
    Tester.test_balanced_image_dataset_from_directory_errors()