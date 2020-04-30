from torch.autograd import Variable
import torch.nn.functional as F
import time
from torch import save
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.optim import SGD
from utils.callback import CallbackList, ProgressBarLogger, DefaultCallback
from typing import Callable, List, Union
from torch.optim import optimizer
from torch.nn import Module
from torch.utils.data import DataLoader
from utils.callback import Callback
from ignite.engine import Events, create_supervised_trainer, create_supervised_evaluator
from ignite.metrics import Accuracy, Loss
from ignite.handlers import ModelCheckpoint
from tqdm import tqdm


#############################
# Method with Igite pytorch #
#############################

def run(model, path_model_checkpoint, path_save_plot, name_model, train_loader, val_loader, epochs, lr, momentum,
        criterion, log_interval, plot_results=True):
    # train_loader, val_loader = get_data_loaders(train_batch_size, val_batch_size)
    # model = Net()
    device = "cpu"

    if torch.cuda.is_available():
        device = "cuda"

    checkpointer = ModelCheckpoint(path_model_checkpoint, name_model, n_saved=2, create_dir=True,
                                   save_as_state_dict=True, require_empty=False)

    model.to(device)  # Move model before creating optimizer
    optimizer = SGD(model.parameters(), lr=lr, momentum=momentum)
    trainer = create_supervised_trainer(model, optimizer, criterion, device=device)
    evaluator = create_supervised_evaluator(
        model, metrics={"accuracy": Accuracy(), "nll": Loss(F.nll_loss)}, device=device
    )

    training_history = {'accuracy': [], 'loss': []}
    validation_history = {'accuracy': [], 'loss': []}
    last_epoch = []

    desc = "ITERATION - loss: {:.2f}"
    pbar = tqdm(initial=0, leave=False, total=len(train_loader), desc=desc.format(0))

    @trainer.on(Events.ITERATION_COMPLETED(every=log_interval))
    def log_training_loss(engine):
        pbar.desc = desc.format(engine.state.output)
        pbar.update(log_interval)

    @trainer.on(Events.EPOCH_COMPLETED)
    def log_training_results(engine):
        pbar.refresh()
        evaluator.run(train_loader)
        metrics = evaluator.state.metrics
        avg_accuracy = metrics["accuracy"]
        avg_nll = metrics["nll"]
        accuracy = metrics['accuracy'] * 100
        training_history['accuracy'].append(accuracy)
        training_history['loss'].append(avg_nll)
        tqdm.write(
            "Training Results - Epoch: {}  Avg accuracy: {:.2f} Avg loss: {:.2f}".format(
                engine.state.epoch, accuracy, avg_nll
            )
        )

    @trainer.on(Events.EPOCH_COMPLETED)
    def log_validation_results(engine):
        evaluator.run(val_loader)
        metrics = evaluator.state.metrics
        avg_accuracy = metrics["accuracy"]
        avg_nll = metrics["nll"]
        accuracy = metrics['accuracy'] * 100
        validation_history['accuracy'].append(accuracy)
        validation_history['loss'].append(avg_nll)
        tqdm.write(
            "Validation Results - Epoch: {}  Avg accuracy: {:.2f} Avg loss: {:.2f}".format(
                engine.state.epoch, accuracy, avg_nll
            )
        )

        pbar.n = pbar.last_print_n = 0

    trainer.add_event_handler(Events.EPOCH_COMPLETED, checkpointer, {'MNIST': model})
    trainer.run(train_loader, max_epochs=epochs)

    if plot_results:
        plt.plot(training_history['accuracy'], label="Training Accuracy")
        plt.plot(validation_history['accuracy'], label="Validation Accuracy")
        plt.xlabel('No. of Epochs')
        plt.ylabel('Accuracy')
        plt.legend(frameon=False)
        plt.savefig(path_save_plot + name_model + '_acc.png')
        plt.show()

        plt.plot(training_history['loss'], label="Training Loss")
        plt.plot(validation_history['loss'], label="Validation Loss")
        plt.xlabel('No. of Epochs')
        plt.ylabel('Loss')
        plt.legend(frameon=False)
        plt.savefig(path_save_plot + name_model + '_loss.png')
        plt.show()

    pbar.close()


def evaluate(model, test_loader):
    device = "cpu"

    if torch.cuda.is_available():
        device = "cuda"

    evaluator_test = create_supervised_evaluator(
        model, metrics={"accuracy": Accuracy(), "nll": Loss(F.nll_loss)}, device=device
    )

    evaluator_test.run(test_loader)
    metrics = evaluator_test.state.metrics
    avg_nll = metrics["nll"]
    accuracy = metrics['accuracy'] * 100
    print(
        "Test Results - Avg accuracy: {:.2f} Avg loss: {:.2f}".format(
            accuracy, avg_nll
        )
    )


###########################
# Old Method with Pytorch #
###########################

def categorical_accuracy(y, y_pred):
    """Calculates categorical accuracy.
    # Arguments:
        y_pred: Prediction probabilities or logits of shape [batch_size, num_categories]
        y: Ground truth categories. Must have shape [batch_size,]
    """
    return torch.eq(y_pred.argmax(dim=-1), y).sum().item() / y_pred.shape[0]


NAMED_METRICS = {
    'categorical_accuracy': categorical_accuracy
}


def gpu_config(model):
    use_gpu = torch.cuda.is_available()
    gpu_count = torch.cuda.device_count()
    # torch.cuda.device(0)
    # torch.cuda.current_device()
    if use_gpu:
        if gpu_count > 1:
            print('use {} gpu who named:'.format(gpu_count))
            for i in range(gpu_count):
                print(torch.cuda.get_device_name(i))
            model = torch.nn.DataParallel(model)
        else:
            print('use 1 gpu who named: {}'.format(torch.cuda.get_device_name(0)))
            model.cuda()
    else:
        print('no gpu available !')
    return model, use_gpu


# Training procedure
def train(use_gpu, model, train_loader, optimizer, slope):
    model.train()
    train_loss = 0
    train_acc = 0

    for batch_idx, (data, target) in enumerate(train_loader):
        # print('batch: {}/{}'.format(batch_idx, len(train_loader)))
        if use_gpu:
            data, target = data.cuda(), target.cuda()
        data, target = Variable(data), Variable(target)
        optimizer.zero_grad()
        output = model((data, slope))
        loss = F.nll_loss(output, target)
        acc = calculate_accuracy(output, target)
        loss.backward()
        optimizer.step()

        train_loss += loss.data
        train_acc += acc.data

    train_loss /= len(train_loader)
    train_loss = train_loss.item()
    train_acc /= len(train_loader)
    train_acc = train_acc.item()
    return train_loss, train_acc


def training(path_save_plot, path_save_model, use_gpu, model, names_model, nb_epoch, train_loader,
             valid_loader, optimizer, plot_result,
             slope_annealing):
    # Slope annealing
    if slope_annealing:
        def get_slope(number_epoch):
            return 1.0 * (1.005 ** (number_epoch - 1))
    else:
        def get_slope(number_epoch):
            return 1.0

    best_valid_loss = float('inf')
    loss_values_train = []
    acc_values_train = []
    loss_values_valid = []
    acc_values_valid = []

    for epoch in range(nb_epoch):
        slope = get_slope(epoch)
        print('# Epoch : {} - Slope : {}'.format(epoch, slope))
        start_time = time.time()
        train_loss, train_acc = train(use_gpu, model, train_loader, optimizer, slope)
        valid_loss, valid_acc = test(use_gpu, model, valid_loader)

        loss_values_train.append(train_loss)
        acc_values_train.append(train_acc)
        loss_values_valid.append(valid_loss)
        acc_values_valid.append(valid_acc)

        if valid_loss < best_valid_loss:
            best_valid_loss = valid_loss
            save(model.state_dict(), path_save_model + names_model + '.pt')

        end_time = time.time()
        epoch_minutes, epoch_secs = epoch_time(start_time, end_time)

        print(f'Epoch: {epoch + 1:02} | Epoch Time: {epoch_minutes}m {epoch_secs}s')
        print(f'\tTrain Loss: {train_loss:.3f} | Train Acc: {train_acc * 100:.2f}%')
        print(f'\t Val. Loss: {valid_loss:.3f} |  Val. Acc: {valid_acc * 100:.2f}%')

    if plot_result:
        plot_loss_acc(loss_values_train, acc_values_train, loss_values_valid, acc_values_valid,
                      path_save_plot, names_model)
    return loss_values_train, acc_values_train, loss_values_valid, acc_values_valid


# Testing procedure
def test(use_gpu, model, test_loader):
    slope = 1.0
    model.eval()
    test_loss = 0.0
    correct = 0.0
    for data, target in test_loader:
        if use_gpu:
            data, target = data.cuda(), target.cuda()
        data, target = Variable(data, volatile=True), Variable(target)
        output = model((data, slope))
        test_loss += F.nll_loss(output, target, size_average=False).item()  # sum up batch loss
        pred = output.data.max(1, keepdim=True)[1]  # get the index of the max log-probability
        correct += pred.eq(target.data.view_as(pred)).cpu().sum()

    test_loss /= len(test_loader.dataset)
    test_acc = correct / len(test_loader.dataset)
    print('Test set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
        test_loss, int(correct), len(test_loader.dataset),
        100. * test_acc))
    return test_loss, test_acc


def calculate_accuracy(fx, y):
    prediction = fx.argmax(1, keepdim=True)
    correct = prediction.eq(y.view_as(prediction)).sum()
    acc = correct.float() / prediction.shape[0]
    return acc


def epoch_time(start_time, end_time):
    elapsed_time = end_time - start_time
    elapsed_minutes = int(elapsed_time / 60)
    elapsed_secs = int(elapsed_time - (elapsed_minutes * 60))
    return elapsed_minutes, elapsed_secs


def plot_loss_acc(loss_values_train, acc_values_train, loss_values_valid, acc_values_valid,
                  path_save_plot, name_model):
    # summarize history for accuracy
    plt.plot(np.array(acc_values_train))
    plt.plot(np.array(acc_values_valid))
    plt.title('model accuracy all_binary_model')
    plt.ylabel('accuracy')
    plt.xlabel('epoch')
    plt.xlim(0, 10)
    plt.legend(['train', 'val'], loc='upper left')
    plt.savefig(path_save_plot + name_model + '_acc.png')
    plt.show()
    # summarize history for loss
    plt.plot(np.array(loss_values_train))
    plt.plot(np.array(loss_values_valid))
    plt.title('model loss all_binary_model')
    plt.ylabel('loss')
    plt.xlabel('epoch')
    plt.xlim(0, 10)
    plt.legend(['train', 'test'], loc='upper left')
    plt.savefig(path_save_plot + name_model + '_loss.png')
    plt.show()
    return


def gradient_step(model: Module, optimiser: optimizer, loss_fn: Callable, x: torch.Tensor, y: torch.Tensor, **kwargs):
    """Takes a single gradient step.
    # Arguments
        model: Model to be fitted
        optimiser: Optimiser to calculate gradient step from loss
        loss_fn: Loss function to calculate between predictions and outputs
        x: Input samples
        y: Input targets
    """
    model.train()
    optimiser.zero_grad()
    y_pred = model((x, slope))
    loss = loss_fn(y_pred, y)
    loss.backward()
    optimiser.step()
    return loss, y_pred


def batch_metrics(model: Module, y_pred: torch.Tensor, y: torch.Tensor, metrics: List[Union[str, Callable]],
                  batch_logs: dict):
    """Calculates metrics for the current training batch
    # Arguments
        model: Model being fit
        y_pred: predictions for a particular batch
        y: labels for a particular batch
        batch_logs: Dictionary of logs for the current batch
    """
    model.eval()
    for m in metrics:
        if isinstance(m, str):
            batch_logs[m] = NAMED_METRICS[m](y, y_pred)
        else:
            # Assume metric is a callable function
            batch_logs = m(y, y_pred)
    return batch_logs


#########################################
# Method for Omniglot few shot learning #
#########################################

def fit(binary_model, slope_annealing, use_gpu, model: Module, optimiser: optimizer, loss_fn: Callable,
        epochs: int, dataloader: DataLoader,
        prepare_batch: Callable, metrics: List[Union[str, Callable]] = None, callbacks: List[Callback] = None,
        verbose: bool = True, fit_function: Callable = gradient_step, fit_function_kwargs: dict = {}):
    """Function to abstract away training loop.
    The benefit of this function is that allows training scripts to be much more readable and allows for easy re-use of
    common training functionality provided they are written as a subclass of voicemap.Callback (following the
    Keras API).
    # Arguments
        model: Model to be fitted.
        optimiser: Optimiser to calculate gradient step from loss
        loss_fn: Loss function to calculate between predictions and outputs
        epochs: Number of epochs of fitting to be performed
        dataloader: `torch.DataLoader` instance to fit the model to
        prepare_batch: Callable to perform any desired preprocessing
        metrics: Optional list of metrics to evaluate the model with
        callbacks: Additional functionality to incorporate into training such as logging metrics to csv, model
            checkpointing, learning rate scheduling etc... See voicemap.callbacks for more.
        verbose: All print output is muted if this argument is `False`
        fit_function: Function for calculating gradients. Leave as default for simple supervised training on labelled
            batches. For more complex training procedures (meta-learning etc...) you will need to write your own
            fit_function
        fit_function_kwargs: Keyword arguments to pass to `fit_function`
    """
    # Determine number of samples:
    num_batches = len(dataloader)
    batch_size = dataloader.batch_size

    callbacks = CallbackList([DefaultCallback(), ] + (callbacks or []) + [ProgressBarLogger(), ])
    callbacks.set_model(model)
    callbacks.set_params({
        'num_batches': num_batches,
        'batch_size': batch_size,
        'verbose': verbose,
        'metrics': (metrics or []),
        'prepare_batch': prepare_batch,
        'loss_fn': loss_fn,
        'optimiser': optimiser
    })

    # Slope annealing
    if slope_annealing:
        def get_slope(epochs):
            return 1.0 * (1.005 ** (epochs - 1))
    else:
        def get_slope(epochs):
            return 1.0
    global slope

    if verbose:
        print('Begin training...')

    callbacks.on_train_begin()

    for epoch in range(1, epochs + 1):
        callbacks.on_epoch_begin(epoch)
        slope = get_slope(epoch)

        epoch_logs = {}
        for batch_index, batch in enumerate(dataloader):
            batch_logs = dict(batch=batch_index, size=(batch_size or 1))

            callbacks.on_batch_begin(batch_index, batch_logs)

            x, y = prepare_batch(batch)

            loss, y_pred = fit_function(binary_model, slope, use_gpu, model, optimiser, loss_fn, x, y,
                                        **fit_function_kwargs)
            batch_logs['loss'] = loss.item()

            # Loops through all metrics
            batch_logs = batch_metrics(model, y_pred, y, metrics, batch_logs)

            callbacks.on_batch_end(batch_index, batch_logs)

        # Run on epoch end
        callbacks.on_epoch_end(epoch, epoch_logs)

    # Run on train end
    if verbose:
        print('Finished.')

    callbacks.on_train_end()
