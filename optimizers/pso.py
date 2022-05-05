import tensorflow as tf
import numpy as np
from numpy.random import uniform
from . import utils


class pso:
    def __init__(
        self,
        loss_op,
        layer_sizes,
        n_iter=2000,
        pop_size=30,
        b=0.9,
        c1=0.8,
        c2=0.5,
        x_min=-1,
        x_max=1,
        gd_alpha=0.00,
        cold_start=True,
        initialization_method=None,
        verbose=False,
    ):
        """The Particle Swarm Optimizer class. Specially built to deal with tensorflow neural networks.
        Args:
            loss_op (function): The fitness function for PSO.
            layer_sizes (list): The layers sizes of the neural net.
            n_iter (int, optional): Number of PSO iterations. Defaults to 2000.
            pop_size (int, optional): Population of the PSO swarm. Defaults to 30.
            b (float, optional): Inertia of the particles. Defaults to 0.9.
            c1 (float, optional): The *p-best* coeficient. Defaults to 0.8.
            c2 (float, optional): The *g-best* coeficient. Defaults to 0.5.
            x_min (int, optional): The min value for the weights generation. Defaults to -1.
            x_max (int, optional): The max value for the weights generation. Defaults to 1.
            gd_alpha (float, optional): Learning rate for gradient descent. Defaults to 0.00, so there wouldn't have any gradient-based optimization.
            cold_start (bool, optional): Set the starting velocities to 0. Defaults to True.
            initialization_method (_type_, optional): Chooses how to initialize the Neural Net weights. Allowed to be one of "uniform", "xavier", or "log_logistic". Defaults to None, where it uses uniform initialization.
            verbose (bool, optional): Shows info during the training . Defaults to False.
        """
        self.loss_op = loss_op
        self.layer_sizes = layer_sizes
        self.pop_size = pop_size
        self.dim = utils.dimensions(layer_sizes)
        self.n_iter = n_iter
        self.b = b
        self.c1 = c1
        self.c2 = c2
        self.x_min = x_min
        self.x_max = x_max
        self.initialization_method = initialization_method
        self.x = self.build_swarm()
        self.p = self.x
        self.loss_history = []
        self.f_p, self.grads = self.fitness_fn(self.p)
        self.g = self.p[tf.math.argmin(input=self.f_p).numpy()[0]]
        self.gd_alpha = gd_alpha
        self.cold_start = cold_start
        self.v = self.start_velocities()
        self.verbose = verbose
        self.name = "PSO" if self.gd_alpha == 0 else "PSO-GD"

    def build_swarm(self):
        """Creates the swarm following the selected initialization method.
        Args:
            initialization_method (str): Chooses how to initialize the Neural Net weights. Allowed to be one of "uniform", "xavier", or "log_logistic". Defaults to None, where it uses uniform initialization.
        Returns:
            tf.Tensor: The PSO swarm population. Each particle represents a neural network.
        """
        return utils.build_NN(
            self.pop_size, self.layer_sizes, self.initialization_method
        )

    def start_velocities(self):
        """Start the velocities of each particle in the population (swarm). If 'self.cold_start' is 'TRUE', the swarm starts with velocity 0, which means stopped.
        Returns:
            tf.Tensor: The starting velocities.
        """
        if self.cold_start:
            return tf.zeros([self.pop_size, self.dim])
        else:
            return tf.Variable(
                tf.random.uniform(
                    [self.pop_size, self.dim],
                    -self.x_max - self.x_min,
                    self.x_max - self.x_min,
                )
            )

    def individual_fn(self, particle):
        """Auxiliary function to get the loss of each particle.
        Args:
            particle (tf.Tensor): One particle of the PSO swarm representing a full neural network.
        Returns:
            tuple: The loss value and the gradients.
        """
        w, b = utils.decode(particle, self.layer_sizes)
        loss, grad = self.loss_op(w, b)
        return loss, utils.flat_grad(grad)

    @tf.function
    def fitness_fn(self, x):
        """Fitness function for the whole swarm.
        Args:
            x (tf.Tensor): The swarm. All the particle's current positions. Which means the weights of all neural networks.
        Returns:
            tuple: the losses and gradients for all particles.
        """
        f_x, grads = tf.vectorized_map(self.individual_fn, x)
        return f_x[:, None], grads

    def get_randoms(self):
        """Generate random values to update the particles' positions.
        Returns:
            _type_: _description_
        """
        return uniform(0, 1, [2, self.dim])[:, None]

    def update_p_best(self):
        """Updates the *p-best* positions."""
        f_x, self.grads = self.fitness_fn(self.x)
        self.loss_history.append(tf.reduce_mean(f_x).numpy())
        self.p = tf.where(f_x < self.f_p, self.x, self.p)
        self.f_p = tf.where(f_x < self.f_p, f_x, self.f_p)

    def update_g_best(self):
        """Update the *g-best* position."""
        self.g = self.p[tf.math.argmin(input=self.f_p).numpy()[0]]

    def step(self):
        """It runs ONE step on the particle swarm optimization."""
        r1, r2 = self.get_randoms()
        self.v = (
            self.b * self.v
            + self.c1 * r1 * (self.p - self.x)
            + self.c2 * r2 * (self.g - self.x)
            - self.gd_alpha * self.grads
        )
        self.x = self.x + self.v
        self.update_p_best()
        self.update_g_best()

    def train(self):
        """The particle swarm optimization. The PSO will optimize the weights according to the losses of the neural network, so this process is actually the neural network training."""
        for i in range(self.n_iter):
            self.step()
            if self.verbose and i % (self.n_iter / 10) == 0:
                utils.progress(
                    (i / self.n_iter) * 100,
                    metric="loss",
                    metricValue=self.loss_history[-1],
                )
        if self.verbose:
            utils.progress(100)
            print()

    def get_best(self):
        """Return the *g-best*, the particle with best results after the training.
        Returns:
            tf.Tensor: the best particle of the swarm.
        """
        return utils.decode(self.g, self.layer_sizes)

    def get_swarm(self):
        """Return the swarm.
        Returns:
            tf.Tensor: The positions of each particle.
        """
        return self.x


def main():
    import matplotlib.pyplot as plt
    import time
    import math
    np.random.seed(42)
    tf.random.set_seed(42)

    # Parameters
    layers = [1] + 3 * [5] + [1]
    pop_size = 100
    n_iter = 2000
    x_min = -1
    x_max = 1
    sample_size = 512
    noise = 0.0

    def objective(x, noise=0):
        return tf.cos(math.pi * x) - x

    def get_loss(X, y):
        def _loss(w, b):
            with tf.GradientTape() as tape:
                tape.watch(w)
                tape.watch(b)
                pred = utils.multilayer_perceptron(w, b, X)
                loss = tf.reduce_mean((y - pred) ** 2)
            trainable_variables = w + b
            grads = tape.gradient(loss, trainable_variables)
            return loss, grads

        return _loss

    X = tf.reshape(
        tf.Variable(np.linspace(x_min, x_max, sample_size), dtype="float32"),
        [sample_size, 1],
    )
    y = objective(X, noise)
    y_min, y_max = tf.math.reduce_min(y), tf.math.reduce_max(y)
    X, y = utils.normalize(X, [x_min, x_max]), utils.normalize(y, [y_min, y_max])

    opt = pso(
        get_loss(X, y),
        layers,
        n_iter,
        pop_size,
        0.9,
        0.8,
        0.5,
        gd_alpha=1e-4,
        x_min=x_min,
        x_max=x_max,
        verbose=True,
    )

    start = time.time()
    opt.train()
    end = time.time()
    print("\nTime elapsed: ", end - start)

    nn_w, nn_b = opt.get_best()

    pred = utils.multilayer_perceptron(nn_w, nn_b, X)

    print("L2 error: ", tf.reduce_mean(tf.pow(y - pred, 2)).numpy())

    plt.plot(tf.squeeze(X), tf.squeeze(y), label="Original Function")
    plt.plot(tf.squeeze(X), tf.squeeze(pred), "--", label="Swarm")
    plt.legend()
    plt.show()

if __name__ == '__main__':
    import sys
    sys.exit(main())