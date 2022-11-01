from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from intel_extension_for_tensorflow.python.test_func import test_util
from intel_extension_for_tensorflow.python.test_func import test
from tensorflow.python.ops import gen_nn_ops

import tensorflow as tf
import numpy as np
import os

from tensorflow.python.framework import constant_op
from tensorflow.python.framework import dtypes
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import gradient_checker
from tensorflow.python.ops import gradients_impl
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import nn_grad
from tensorflow.python.ops import nn_impl
from tensorflow.python.ops import nn_ops

os.environ['ITEX_ENABLE_ONEDNN_LAYOUT_OPT']="0"

class BatchNormalizationTest(test.TestCase):
  def _test_training_bwd(self,
                     x_shape,
                     x_dtype,
                     scale_shape,
                     scale_dtype,
                     use_gpu,
                     exponential_avg_factor=1.0,
                     data_format='NHWC'):
    np.random.seed(1)
    x_val = np.random.random_sample(x_shape).astype(x_dtype)
    dy_val = np.random.random_sample(x_shape).astype(x_dtype)    
    scale_val = np.random.random_sample(scale_shape).astype(scale_dtype)
    reserved_val = np.random.random_sample(scale_shape).astype(scale_dtype)
    
    with tf.device("cpu"):
      batch_mean, batch_var = nn_impl.moments(
        math_ops.cast(x_val, float), [0, 1, 2], keep_dims=False)
        
    device_str = "xpu" if use_gpu else "cpu"
    with tf.device(device_str):
      x = constant_op.constant(x_val, name='x')
      dy = constant_op.constant(dy_val, name='dy')
      scale = constant_op.constant(scale_val, name='scale')
      reserved = constant_op.constant(reserved_val, name='reserved')
      dx, dscale, doffset, _, _ = gen_nn_ops.fused_batch_norm_grad_v3(
          dy,
          x,
          scale,
          batch_mean,
          batch_var,
          reserved,
          data_format='NHWC',
          is_training=True)
      return dx, dscale, doffset    

  def _test_training(self,
                     x_shape,
                     x_dtype,
                     scale_shape,
                     scale_dtype,
                     use_gpu,
                     exponential_avg_factor=1.0,
                     data_format='NHWC'):
    np.random.seed(1)
    x_val = np.random.random_sample(x_shape).astype(x_dtype)
    scale_val = np.random.random_sample(scale_shape).astype(scale_dtype)
    offset_val = np.random.random_sample(scale_shape).astype(scale_dtype)
    if exponential_avg_factor == 1.0:
      old_mean_val = None
      old_var_val = None
    else:
      old_mean_val = np.random.random_sample(scale_shape).astype(scale_dtype)
      old_var_val = np.random.random_sample(scale_shape).astype(scale_dtype)
    device_str = "xpu" if use_gpu else "cpu"
    with tf.device(device_str):
      x = constant_op.constant(x_val, name='x')
      scale = constant_op.constant(scale_val, name='scale')
      offset = constant_op.constant(offset_val, name='offset')
      epsilon = 0.001
      y, mean, var = array_ops.identity_n(nn_impl.fused_batch_norm(
          x,
          scale,
          offset,
          mean=old_mean_val,
          variance=old_var_val,
          epsilon=epsilon,
          exponential_avg_factor=exponential_avg_factor,
          data_format=data_format,
          is_training=True))
      return y, mean, var
    
  # only test on GPU
  def testShapeInRN50(self):
    if not test.is_gpu_available():
      return;
    bs_lst = [1]
    h_lst = [112, 7, 14, 28]
    c_lst = [16, 64, 128, 256]
    dtype_lst = [np.float32, tf.dtypes.bfloat16.as_numpy_dtype]
    for dtype in dtype_lst:
      for bs in bs_lst:
          for h in h_lst:
            for c in c_lst:
              x_shape=[bs, h, h, c]          
              y, mean, var = self._test_training(
                          x_shape,
                          dtype,
                          [c],
                          np.float32,
                          use_gpu=True,
                          exponential_avg_factor=1.0,
                          data_format='NHWC')   
              ref_y, ref_mean, ref_var = self._test_training(
                          x_shape,
                          dtype,
                          [c],
                          np.float32,
                          use_gpu=False,
                          exponential_avg_factor=1.0,
                          data_format='NHWC')              
              self.assertAllCloseAccordingToType(ref_mean[-10:], mean[-10:], float_rtol=1e-3, float_atol=1e-3)
              self.assertAllCloseAccordingToType(ref_var[-10:], var[-10:], float_rtol=1e-3, float_atol=1e-3)       
              self.assertAllCloseAccordingToType(ref_y[0, 0, 0, -10:], y[0, 0, 0, -10:], float_rtol=1e-3, float_atol=1e-3)       
   
          
  # only test on GPU
  def testShapeInRN50BWD(self):
    if not test.is_gpu_available():
      return;
    bs_lst = [1]
    h_lst = [7, 14, 28, 56, 112]
    c_lst = [16, 64, 128, 256, 512]
    dtype_lst = [np.float32, tf.dtypes.bfloat16.as_numpy_dtype]
    for dtype in dtype_lst:    
      for bs in bs_lst:
        for h in h_lst:
          for c in c_lst:
            x_shape=[bs, h, h, c]
            
            dx, dscale, doffset = self._test_training_bwd(
                        x_shape,
                        dtype,
                        [c],
                        np.float32,
                        use_gpu=True,
                        exponential_avg_factor=1.0,
                        data_format='NHWC')   
            ref_dx, ref_dscale, ref_doffset = self._test_training_bwd(
                        x_shape,
                        dtype,
                        [c],
                        np.float32,
                        use_gpu=False,
                        exponential_avg_factor=1.0,
                        data_format='NHWC')    
            self.assertAllCloseAccordingToType(ref_dscale[-10:], dscale[-10:], float_rtol=1e-3, float_atol=1e-3)        
            self.assertAllCloseAccordingToType(ref_doffset[-10:], doffset[-10:], float_rtol=1e-3, float_atol=1e-3)        
            self.assertAllCloseAccordingToType(ref_dx[0, 0, 0, -10:], dx[0, 0, 0, -10:], float_rtol=1e-3, float_atol=1e-3)        
                                        
  
if __name__ == '__main__':
  test.main()
