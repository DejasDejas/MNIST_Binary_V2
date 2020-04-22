import sys

sys.path.append('')

import torch.nn.functional as F
from utils.models import get_my_model_Omniglot
from DataLoader.dataLoaders import get_omniglot_dataloaders_classification
from utils.training import run

batch_size_train = 64
batch_size_test = 64
# Dataset
train_loader, valid_loader, test_loader = get_omniglot_dataloaders_classification(batch_size_train, batch_size_test)

# parameters default values
epochs = 50
lr = 1e-3
momentum = 0.9
log_interval = 10  # how many batches to wait before logging training status
criterion = F.nll_loss

# parameters model to load no Binary model
#binary = False
#model_no_binary, name_model = get_my_model_Omniglot(binary)
#print(name_model)

#path_model_checkpoint_no_binary = 'trained_models/Omniglot_classif/No_binary_models/'
#path_save_plot_no_binary = 'results/Omniglot_results/plot_acc_loss/Omniglot_classif/'

#print('Begin running No Binary model')
#run(model_no_binary, path_model_checkpoint_no_binary, path_save_plot_no_binary, name_model, train_loader, valid_loader,
#    epochs, lr, momentum, criterion, log_interval)
#print('End running No Binary model')

# parameters model to load no Binary model
binary = True
model_binary, name_model = get_my_model_Omniglot(binary)
print(name_model)

path_model_checkpoint_binary = 'trained_models/Omniglot_classif/Binary_models/'
path_save_plot_binary = 'results/Omniglot_results/plot_acc_loss/Omniglot_classif/'

print('Begin running Binary model')
run(model_binary, path_model_checkpoint_binary, path_save_plot_binary, name_model, train_loader, valid_loader, epochs,
    lr, momentum, criterion, log_interval)
print('End running Binary model')
