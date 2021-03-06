import tensorflow as tf
import tensorflow_probability as tfp
import numpy as np
from normalizing_flows.flows import Transform
from normalizing_flows.utils import var

@tf.function
def act_norm(x, log_s, b, inverse=tf.constant(False)):
    shape = tf.shape(x)
    hw = tf.cast(tf.math.reduce_prod(shape[1:-1]), tf.float32)
    ldj = tf.math.reduce_sum(log_s)*tf.ones(shape[:1])*hw
    if inverse:
        y = tf.math.exp(-log_s)*x - b
        ldj = -ldj
    else:
        y = tf.math.exp(log_s)*(x + b)
    return y, ldj
    
class ActNorm(Transform):
    def __init__(self, input_shape=None, alpha=1.0E-4, name='actnorm', *args, **kwargs):    
        """
        Creates a new activation normalization (actnorm) transform.
        """
        self.alpha = alpha
        self.log_s = None
        self.b = None
        self.init = False
        super().__init__(*args,
                         input_shape=input_shape,
                         requires_init=True,
                         has_constant_ldj=True,
                         name=name, **kwargs)
        
    def _initialize(self, input_shape):
        if not self.init:
            mus = tf.random.normal([1 for _ in range(input_shape.rank-1)] + [input_shape[-1]], mean=0.0, stddev=0.1)
            log_sigmas = tf.random.normal([1 for _ in range(input_shape.rank-1)] + [input_shape[-1]], mean=0.0, stddev=0.1)
            self.log_s = tf.Variable(log_sigmas, name=f'{self.name}/log_s')
            self.b = tf.Variable(mus, name=f'{self.name}/b')
            self.init = True
            
    def _init_from_data(self, x):
        # assign initial values based on mean/stdev of first batch
        input_shape = x.shape
        mus = tf.math.reduce_mean(x, axis=[i for i in range(input_shape.rank-1)], keepdims=True)
        if tf.math.reduce_sum(tf.shape(x)[1:-1]) > 2:
            sigmas = tf.math.reduce_std(x, axis=[i for i in range(input_shape.rank-1)], keepdims=True)
        else:
            # if all non-channel dimensions have only one element, initialize with ones to avoid inf values
            sigmas = tf.ones(input_shape)
        self.log_s.assign(-tf.math.log(sigmas))
        self.b.assign(-mus)
        self.init_from_data = False

    def _forward(self, x, **kwargs):
        if 'init' in kwargs and kwargs['init']:
            self._init_from_data(x)
        return act_norm(x, var(self.log_s), var(self.b))
        
    def _inverse(self, y, **kwargs):
        if 'init' in kwargs and kwargs['init']:
            self._init_from_data(y)
        return act_norm(y, var(self.log_s), var(self.b), inverse=tf.constant(True))
    
    def _regularization_loss(self):
        return self.alpha*tf.math.reduce_sum(self.log_s**2)