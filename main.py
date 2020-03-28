from torch.cuda import is_available
import torch.optim as optim
from DataLoader.dataLoaders import get_mnist_dataloaders
from utils.training import training, test
from torch import load
from visualize.viz import visTensor, visualize_activations
import matplotlib.pyplot as plt

from utils.models import NonBinaryNet, BinaryNet

"""
Code source: https://github.com/Wizaron/binary-stochastic-neurons
"""

# parameters default values
lr = 0.1
momentum = 0.9
nb_epoch = 10
batch_size_train = 64
batch_size_test = 1000
slope_annealing = False
reinforce = False
stochastic = True
binary = True
plot_result = True

# Model, activation type, estimator type
if binary:
    if stochastic:
        mode = 'Stochastic'
        names_model = 'Stochastic'
    else:
        mode = 'Deterministic'
        names_model = 'Deterministic'
    if reinforce:
        estimator = 'REINFORCE'
        names_model += '_REINFORCE_'
    else:
        estimator = 'ST'
        names_model += '_ST_'
    model = BinaryNet(mode=mode, estimator=estimator)
else:
    model = NonBinaryNet()
    names_model = 'NonBinaryNet'
    mode = None
    estimator = None

# Cuda
use_gpu = is_available()
if use_gpu:
    model.cuda()

# Dataset
train_loader, valid_loader, test_loader, classes = get_mnist_dataloaders(batch_size_train, batch_size_test)

# Slope annealing
if slope_annealing:
    get_slope = lambda epoch: 1.0 * (1.005 ** (epoch - 1))
else:
    get_slope = lambda epoch: 1.0

# TODO: create conv layer to have 2 layer CNN

# train
# optimizer
# optimizer = optim.SGD(model.parameters(), lr=lr, momentum=momentum)
# train_loss, train_acc, val_loss, val_acc = training(use_gpu, model, names_model, nb_epoch, train_loader, valid_loader,
#                                                    optimizer, plot_result, get_slope)
# test
model.load_state_dict(load('./trained_models/MNIST/' + names_model + '.pt'))
# test_loss, test_acc = test(use_gpu, model, test_loader, nb_epoch, get_slope)

"""
# visualise activations
visualize_activations(model, get_slope)

# visualize filters
filters = model.layer1[0].weight.data.clone()
visTensor(filters.cpu(), ch=0, allkernels=False)
plt.ioff()
plt.show()
"""