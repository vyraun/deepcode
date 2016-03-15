#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# File: utils.py
# @Author: Lisa Wang
# @created: Jan 29 2016
#
#==============================================================================
# DESCRIPTION:
# A place to put useful functions, e.g. for transforming data, printing, etc.
#==============================================================================
# CURRENT STATUS: In progress/ working! :) 
#==============================================================================
# USAGE: 
# import utils or from utils import *
#==============================================================================
#
###############################################################################

import numpy as np
import time
import pickle
import random
from constants import *
from sklearn.utils import shuffle


def save_ast_embeddings(ast_embeddings, hoc_num, description=''):
    if description != '':
        np.save(AST_EMBEDDINGS_PREFIX + str(hoc_num) + '_' + description + MAT_SUFFIX, ast_embeddings)
    else:
        p.save(AST_EMBEDDINGS_PREFIX + str(hoc_num) + MAT_SUFFIX, ast_embeddings)

# ############################# Batch iterator ###############################
# This is just a simple helper function iterating over training data in
# mini-batches of a particular size, optionally in random order. It assumes
# data is available as numpy arrays. For big datasets, you could load numpy
# arrays as memory-mapped files (np.load(..., mmap_mode='r')), or write your
# own custom data iteration function. For small datasets, you can also copy
# them to GPU at once for slightly improved performance. This would involve
# several changes in the main program, though, and is not demonstrated here.
# taken from lasagne mnist example.
def iterate_minibatches(X, next_problem, truth, batchsize, shuffle=False):
    assert(X.shape[0] == truth.shape[0])
    assert(X.shape[0] == next_problem.shape[0])
    num_samples = X.shape[0]
    if shuffle:
        indices = np.arange(num_samples)
        np.random.shuffle(indices)
    for start_idx in range(0, num_samples - batchsize + 1, batchsize):
        if shuffle:
            excerpt = indices[start_idx:start_idx + batchsize]
        else:
            excerpt = slice(start_idx, start_idx + batchsize)
        yield X[excerpt], next_problem[excerpt], truth[excerpt]

# better version that is flexible in terms of input
# data is a list of matrices for a data set, for example [X, y]
# or [X, next_problem, y]
def iter_minibatches(data, batchsize, shuffle=False):
    X = data[0]
    num_samples = X.shape[0]
    if shuffle:
        indices = np.arange(num_samples)
        np.random.shuffle(indices)
    for start_idx in range(0, num_samples - batchsize + 1, batchsize):
        if shuffle:
            excerpt = indices[start_idx:start_idx + batchsize]
        else:
            excerpt = slice(start_idx, start_idx + batchsize)
        yield [d[excerpt] for d in data]


# just a test to make sure that iterate_minibatches works!
# batchsize = 50
# for batch in utils.iterate_minibatches(X_train, next_problem_train, truth_train, batchsize, shuffle=False):
#     X_, next_problem_, truth_  = batch
#     print X_.shape
#     print next_problem_.shape


# To use on synthetic data set
# DEPRECATED VERSION
# TODO: REMOVE THIS AFTER WE DETERMINED THAT NO PROGRAM STILL USES IT
def vectorize_syn_data(data_raw, num_timesteps):
    num_samples = data_raw.shape[0]
    num_problems = data_raw.shape[1]
    X = np.zeros((num_samples, num_timesteps, num_problems * 2), dtype=np.bool)
    y = np.zeros((num_samples, num_timesteps), dtype=np.int)

    # Create 3-dimensional input tensor with one-hot encodings for each sample
    # the dimension of each vector for a student i and time t is 2 * num_problems
    # where the first half corresponds to the correctly answered problems and the
    # second half to the incorrectly answered ones.
    for i in xrange(num_samples):
        
        # for the first time step. Done separately so we can populate the output 
        # tensor at the same time, which is shifted back by 1.

        for t in xrange(0,num_timesteps):
            p = t # since timestep t corresponds to problem p where t=p
            if data_raw[i,p] == 1:
                X[i, t, p] = 1 
            else:
                X[i, t, num_problems + p] = 1
            # this is a special case for the synthetic data set, where the next problem 
            # is just the current problem index + 1
            y[i,t] = p + 1
    corr = np.copy(data_raw) # Correctness indicates which problem a student has answered correctly
    return X, y, corr


def vectorize_data(data_raw):
    """
    inputs: 
        - data_raw of shape (num_samples, num_problems)
    outputs:
        - X, which is the input to the RNN, shape(num_samples, num_timesteps, num_problems * 2)
        - next_problem: for each student, indicates which problem the student is solving next. 
                        one hot encoding : shape (num_samples, num_timesteps, num_problems)
        - truth: for each student, indicates whether student answers problem at next time step
               correctly. shape(num_samples, num_timesteps)

        notice that num_timesteps can be at most num_problems - 1, since we need 
        to predict on the last input, whether student answers next problem correctly.
    """

    num_samples = data_raw.shape[0]
    num_problems = data_raw.shape[1]
    num_timesteps = num_problems - 1

    X = np.zeros((num_samples, num_timesteps, num_problems * 2), dtype=np.bool)
    next_problem = np.zeros((num_samples, num_timesteps, num_problems), dtype=np.int)
    truth = np.zeros((num_samples, num_timesteps), dtype=np.int)

    # Create 3-dimensional input tensor with one-hot encodings for each sample
    # the dimension of each vector for a student i and time t is 2 * num_problems
    # where the first half corresponds to the correctly answered problems and the
    # second half to the incorrectly answered ones.
    for i in xrange(num_samples):
        
        # for the first time step. Done separately so we can populate the output 
        # tensor at the same time, which is shifted back by 1.

        for t in xrange(0,num_timesteps):
            p = t # since timestep t corresponds to problem p where t=p
            if data_raw[i,p] == 1:
                X[i, t, p] = 1 
            else:
                X[i, t, num_problems + p] = 1
            # this is a special case for the synthetic data set, where the next problem 
            # is just the current problem index + 1
            next_problem[i,t, p+1] = 1
            # truth tells us whether student i answers problem at next time step correctly
            truth[i,t] = data_raw[i,t+1] 
    # truth = np.copy(data_raw) 
    # truth = truth[:, 1:]
    return X, next_problem, truth

def prepare_traj_data_for_rnn(raw_matrix):
    """
    inputs: 
        - raw_matrix of shape (num_traj, max_traj_len, num_asts)
    outputs:
        - X, which is the input to the RNN, shape(num_traj, num_timesteps, num_asts)
        - y: truth vector. shape(num_traj, num_timesteps, num_asts)
    """
    (num_traj, max_traj_len, num_asts) = raw_matrix.shape
    # notice that num_timesteps can be at most max_traj_len - 1, since we need 
    # to be able to predict on the last input and have a truth value.  
    num_timesteps = max_traj_len - 1

    X = np.copy(raw_matrix[:,:-1,:])

    # y = np.copy(raw_matrix[:,1:,:])

    # alternative version where y has shape (num_traj, num_timesteps)
    # and the values are the indices corresponding to the correct ast prediction
    # instead of one-hot encoding
    y = np.zeros((num_traj, num_timesteps))
    for n in xrange(num_traj):
        for t in xrange(num_timesteps):
            y[n,t] = np.argmax(raw_matrix[n,t+1,:])

    return X, y

def prepare_traj_data_for_rnn_using_embeddings(traj_mat, ast_embeddings, traj_row_to_ast_id_map, embed_ast_id_to_row_map):
    """
    inputs: 
        - raw_matrix of shape (num_traj, max_traj_len, num_asts)
    outputs:
        - X, which is the input to the RNN, shape(num_traj, num_timesteps, num_asts)
        - y: truth vector. shape(num_traj, num_timesteps, num_asts)
    """
    (num_traj, max_traj_len, num_asts) = traj_mat.shape
    # notice that num_timesteps can be at most max_traj_len - 1, since we need 
    # to be able to predict on the last input and have a truth value.  
    num_timesteps = max_traj_len - 1

    num_ast_embeddings, embed_dim = ast_embeddings.shape
    print num_asts
    print num_ast_embeddings

    X = np.zeros((num_traj, num_timesteps, embed_dim))
    y = np.zeros((num_traj, num_timesteps))
    for n in xrange(num_traj):
        for t in xrange(num_timesteps):
            ast_row = np.argmax(traj_mat[n,t,:])
            X[n,t,:] = get_embedding_for_ast(ast_row, ast_embeddings, traj_row_to_ast_id_map, embed_ast_id_to_row_map)
            y[n,t] = np.argmax(traj_mat[n,t+1,:])
    return X, y

def get_embedding_for_ast(traj_mat_ast_row, ast_embeddings, traj_row_to_ast_id_map, embed_ast_id_to_row_map):
    num_ast_embeddings, embed_dim = ast_embeddings.shape
    ast_id = int(traj_row_to_ast_id_map[traj_mat_ast_row])

    if ast_id != -1:
        embed_ast_row = int(embed_ast_id_to_row_map[ast_id])
        return ast_embeddings[embed_ast_row,:].reshape((embed_dim,))
    else:
        return np.zeros((embed_dim,))

    
def prepare_block_data_for_rnn(raw_matrix):
    """
    inputs: 
        - raw_matrix of shape (num_traj, max_traj_len, num_asts)
    outputs:
        - X, which is the input to the RNN, shape(num_asts, num_timesteps, num_blocks)
        - mask, which masks out all the values in the X tensor which don't
            correspond to any sequence. (since some sequences are shorter 
                than num_timesteps), shape(num_asts, num_timesteps)
        - y: truth vector. the correct next block.
               shape(num_asts, num_timesteps)
    """
    (num_asts, max_ast_len, num_blocks) = raw_matrix.shape
    # notice that num_timesteps can be at most max_traj_len - 1, since we need 
    # to be able to predict on the last input and have a truth value.  
    num_timesteps = max_ast_len - 1

    X = np.copy(raw_matrix[:,:-1,:])
    mask = np.ones((num_asts, num_timesteps)).astype('uint8')
    
    for n in xrange(num_asts):
        for t in xrange(num_timesteps-1):
            # if the ast block sequence already ended (as indicated by dummy block
            # at index 0, then mask out) We want to predict only up until the
            # the second to last elem in the sequence
            if X[n,t+1,0] == 1:
                mask[n,t] = 0
        if X[n,num_timesteps-1,0] == 1:
            mask[n,num_timesteps-1] = 0

    # y has shape (num_asts, num_timesteps)
    # and the values are the indices corresponding to the correct ast prediction
    # instead of one-hot encoding
    y = np.zeros((num_asts, num_timesteps))
    for n in xrange(num_asts):
        for t in xrange(num_timesteps):
            y[n,t] = np.argmax(raw_matrix[n,t+1,:])

    return X, mask, y

def convert_data_to_ast_ids(data, row_to_ast_id_map):

    '''
    INPUT:
    data = (X,y)
    X: (batchsize, num_timesteps, num_asts)
    y: (batchsize, num_timesteps)

    OUTPUT:
    X_ast_ids: (batchsize, num_timesteps), containing ast ids, which we can
            use to look up ast json files.
    y_ast_ids: (batchsize, num_timesteps)

    '''

    X, y = data
    batchsize, num_timesteps, num_asts = X.shape
    X_ast_ids = np.zeros((batchsize, num_timesteps))
    y_ast_ids = np.zeros((batchsize, num_timesteps))

    for n in xrange(batchsize):
        for t in xrange(num_timesteps):
            y_ast_ids[n,t] = row_to_ast_id_map[int(y[n,t])]
            X_ast_ids[n,t] = row_to_ast_id_map[np.argmax(X[n,t,:])]

    return X_ast_ids, y_ast_ids

def convert_truth_to_ast_ids(y, row_to_ast_id_map):
    '''
    INPUT:
    y: (batchsize, num_timesteps)

    OUTPUT:
    y_ast_ids: (batchsize, num_timesteps)
    '''
    batchsize, num_timesteps = y.shape
    y_ast_ids = np.zeros((batchsize, num_timesteps))

    for n in xrange(batchsize):
        for t in xrange(num_timesteps):
            y_ast_ids[n,t] = row_to_ast_id_map[int(y[n,t])]

    return y_ast_ids

def convert_ast_or_block_data_to_ids(X, y, row_to_id_map):

    '''
    INPUT:
    data = (X,y)
    X: (batchsize, num_timesteps, num_asts)
    y: (batchsize, num_timestep)

    OUTPUT:
    X_ast_ids: (batchsize, num_timesteps), containing ast ids, which we can
            use to look up ast json files.
    y_ast_ids: (batchsize, num_timesteps)

    '''
    batchsize, num_timesteps, _ = X.shape
    X_ids = np.zeros((batchsize, num_timesteps))
    y_ids = np.zeros((batchsize, num_timesteps))

    for n in xrange(batchsize):
        for t in xrange(num_timesteps):
            y_ids[n,t] = row_to_id_map[int(y[n,t])]
            X_ids[n,t] = row_to_id_map[np.argmax(X[n,t,:])]

    return X_ids, y_ids



def convert_pred_to_ast_ids(pred, row_to_ast_id_map):
    batchsize, num_timesteps, num_asts = pred.shape
    pred_ast_ids = np.zeros((batchsize, num_timesteps))
    for n in xrange(batchsize):
        for t in xrange(num_timesteps):
            pred_ast_ids[n,t] = row_to_ast_id_map[np.argmax(pred[n,t,:])]
    
    return pred_ast_ids


def load_dataset_predict_ast(hoc_num=7, data_sz=-1):
    print('Preparing network inputs and targets, and the ast maps...')
    hoc_num = str(hoc_num)
    data_set = 'hoc' + hoc_num
    # if DATA_SZ = -1, use entire data set
    # For DATA_SZ, powers of 2 work best for performance.
    ast_map_file = TRAJ_AST_MAP_PREFIX + hoc_num + MAP_SUFFIX

    # Load AST ID to Row Map
    ast_id_to_row_map = pickle.load(open( ast_map_file, "rb" ))
    # Create Row to AST ID Map by inverting the previous one
    row_to_ast_id_map = {v: k for k, v in ast_id_to_row_map.items()}
    # trajectories matrix for a single hoc exercise
    # shape (num_traj, max_traj_len, num_asts)
    # Note that ast_index = 0 corresponds to the <END> token,
    # marking that the student has already finished.
    # The <END> token does not correspond to an AST.

    traj_mat_file = TRAJ_MAP_PREFIX + hoc_num + MAT_SUFFIX
    traj_mat = np.load(traj_mat_file)

    # if data_sz specified, reduce matrix. 
    # Useful to create smaller data sets for testing purposes.
    if data_sz != -1:
        traj_mat = traj_mat[:data_sz]
    print 'Trajectory matrix shape {}'.format(traj_mat.shape)

    # shuffle the first dimension of the matrix
    np.random.shuffle(traj_mat)

    num_traj, max_traj_len, num_asts = traj_mat.shape
    # Split data into train, val, test
    # TODO: Replace with kfold validation in the future
    # perhaps we can use sklearn kfold?
    train_mat = traj_mat[0:7*num_traj/8,:]
    val_mat =  traj_mat[7*num_traj/8: 15*num_traj/16 ,:]
    test_mat = traj_mat[15*num_traj/16:num_traj,:]

    train_data = prepare_traj_data_for_rnn(train_mat)
    val_data = prepare_traj_data_for_rnn(val_mat)
    test_data = prepare_traj_data_for_rnn(test_mat)


    X_train, y_train = train_data
    X_val, y_val = val_data
    X_test, y_test = test_data
    print 'X_train shape {}'.format(X_train.shape)
    print 'y_train shape {}'.format(y_train.shape)
    print 'X_val shape {}'.format(X_val.shape)
    print 'X_test shape {}'.format(X_test.shape)
    num_train, num_timesteps, num_asts = X_train.shape

    # print y_train[:10]
    # print X_train[:10,:, :10]

    X_train_ast_ids, y_train_ast_ids = convert_data_to_ast_ids(train_data, row_to_ast_id_map)
    # print X_train_ast_ids[:10]
    # print y_train_ast_ids[:10]
    print 'num_timesteps {}'.format(num_timesteps)
    print ("Inputs and targets done!")
    return train_data, val_data, test_data, ast_id_to_row_map, row_to_ast_id_map, num_timesteps, num_asts


def load_dataset_predict_block_all_hocs():
    X_all_hocs = []
    mask_all_hocs = []
    y_all_hocs = []
    hocs_samples_count = []
    split_indices =  []
    hoc_to_indices = {}
    total_count = 0
    for hoc in xrange(1,10):
        train_data, val_data, test_data, all_data, num_timesteps, num_blocks  = load_dataset_predict_block(hoc_num=hoc)
        X, mask, y = all_data
        X_all_hocs.append(X)
        mask_all_hocs.append(mask)
        y_all_hocs.append(y)
        hocs_samples_count.append(all_data[0].shape[0])
        total_count += all_data[0].shape[0]
        split_indices.append(total_count)
    
    # we don't need the last split index for np.split(), otherwise the last 
    # split will be an empty array
    del split_indices[-1]
    X_all_hocs_mat = reduce(lambda a,b: np.concatenate([a,b], axis=0), X_all_hocs)
    mask_all_hocs_mat = reduce(lambda a,b: np.concatenate([a,b], axis=0), mask_all_hocs)
    y_all_hocs_mat = reduce(lambda a,b: np.concatenate([a,b], axis=0), y_all_hocs)

    return X_all_hocs_mat, mask_all_hocs_mat, y_all_hocs_mat, split_indices


def load_dataset_predict_block(hoc_num=7, data_sz=-1):
    print('Preparing network inputs and targets, and the block maps for hoc {}'.format(hoc_num))
    hoc_num = str(hoc_num)
    data_set = 'hoc' + hoc_num
    # if DATA_SZ = -1, use entire data set
    # For DATA_SZ, powers of 2 work best for performance.


    # block_map_file = '../processed_data/map_block_string_to_block_id' + hoc_num + '.pickle'

    # # Load AST ID to Row Map
    # block_id_to_row_map = pickle.load(open( block_map_file, "rb" ))
    # # Create Row to AST ID Map by inverting the previous one
    # row_to_block_id_map = {v: k for k, v in block_id_to_row_map.items()}


    # trajectories matrix for a single hoc exercise
    # shape (num_traj, max_traj_len, num_blocks)
    # Note that block_index = 0 corresponds to the <END> token,
    # marking that the student has already finished.
    # The <END> token does not correspond to an AST.
    # all_data has the asts in the same order as the original ast_mat.
    # train, val and test are shuffled, so the ast_rows don't correspond
    # to the initial rows in ast_mat, meaining the mapping ast_row to ast_id 
    # does not apply to them.
    
    ast_mat = np.load(BLOCK_MAT_PREFIX + hoc_num + BLOCK_LIMIT_TIMESTEPS +  MAT_SUFFIX)

    # if data_sz specified, reduce matrix. 
    # Useful to create smaller data sets for testing purposes.
    if data_sz != -1:
        ast_mat = ast_mat[:data_sz]
    # print 'Trajectory matrix shape {}'.format(ast_mat.shape)

    # shuffle the first dimension of the matrix
    np.random.shuffle(ast_mat)

    num_asts, max_ast_len, num_blocks = ast_mat.shape

    all_data = prepare_block_data_for_rnn(ast_mat)
    # Split data into train, val, test
    # TODO: Replace with kfold validation in the future
    # perhaps we can use sklearn kfold?

    ast_mat = shuffle(ast_mat)
    train_mat = ast_mat[0:7*num_asts/8,:]
    val_mat =  ast_mat[7*num_asts/8: 15*num_asts/16 ,:]
    test_mat = ast_mat[15*num_asts/16:num_asts,:]

    train_data = prepare_block_data_for_rnn(train_mat)
    val_data = prepare_block_data_for_rnn(val_mat)
    test_data = prepare_block_data_for_rnn(test_mat)

    num_timesteps = train_data[0].shape[1]

    # print ("Inputs and targets done!")
    # return train_data, val_data, test_data, block_id_to_row_map, row_to_block_id_map, num_timesteps, num_blocks
    return train_data, val_data, test_data, all_data, num_timesteps, num_blocks

def save_ast_embeddings(ast_embeddings, hoc_num):
    np.save(AST_EMBEDDINGS_PREFIX + str(hoc_num) + MAT_SUFFIX, ast_embeddings)

def save_ast_embeddings_for_all_hocs(ast_embeddings, split_indices):
    """ input: matrix with embeddings for asts across all HOCs. 
        We need to split up this matrix by asts, using the split_indices list 
        we created when we concatenated the data across all hocs.
    """
    ast_embeddings_list = np.split(ast_embeddings, split_indices)
    for hoc in xrange(HOC_MIN, HOC_MAX + 1):
        save_ast_embeddings(ast_embeddings_list[hoc - 1], hoc)


def load_dataset_predict_ast_using_embeddings(hoc_num=2, data_sz=-1):
    # if DATA_SZ = -1, use entire data set
    # For DATA_SZ, powers of 2 work best for performance.

    print('Preparing network inputs and targets, and the ast maps...')
    hoc_num = str(hoc_num)
    data_set = 'hoc' + hoc_num

    # trajectories matrix for a single hoc exercise
    # shape (num_traj, max_traj_len, num_asts)
    # Note that ast_index = 0 corresponds to the <END> token,
    # marking that the student has already finished.
    # The <END> token does not correspond to an AST.
    traj_mat_file = TRAJ_MAP_PREFIX + hoc_num + MAT_SUFFIX
    traj_mat = np.load(traj_mat_file)
    
    traj_ast_map_file = TRAJ_AST_MAP_PREFIX + hoc_num + MAP_SUFFIX
    # Load AST ID to Row Map for trajectory matrix
    traj_ast_id_to_row_map = pickle.load(open( traj_ast_map_file, "rb" ))
    traj_row_to_ast_id_map = {v: k for k, v in traj_ast_id_to_row_map.items()}

    ast_embeddings = np.load(AST_EMBEDDINGS_PREFIX + str(hoc_num) + MAT_SUFFIX)

    embed_ast_map_file = EMBED_AST_MAP_PREFIX + hoc_num + MAP_SUFFIX
    embed_row_to_ast_id_map = pickle.load(open(embed_ast_map_file, "rb"))
    embed_ast_id_to_row_map = {v: k for k, v in embed_row_to_ast_id_map.items()}

    ast_maps = {
        'traj_id_to_row': traj_ast_id_to_row_map,
        'traj_row_to_id' : traj_row_to_ast_id_map,
        'embed_id_to_row' : embed_ast_id_to_row_map,
        'embed_row_to_id' : embed_row_to_ast_id_map,
    }

    # if data_sz specified, reduce matrix. 
    # Useful to create smaller data sets for testing purposes.
    if data_sz != -1:
        traj_mat = traj_mat[:data_sz]
    print 'Trajectory matrix shape {}'.format(traj_mat.shape)
    num_asts = traj_mat.shape[2]

    # shuffle the first dimension of the matrix
    np.random.shuffle(traj_mat)

    X, y = prepare_traj_data_for_rnn_using_embeddings(traj_mat, ast_embeddings, traj_row_to_ast_id_map, embed_ast_id_to_row_map)

    print ("Inputs and targets done!")
    return  X, y, ast_maps, num_asts


def print_sample_program(hoc_num=7, ast_id=0):
    hoc_num = str(hoc_num)
    embed_ast_map_file = EMBED_AST_MAP_PREFIX + hoc_num + MAP_SUFFIX
    embed_row_to_ast_id_map = pickle.load(open(embed_ast_map_file, "rb"))
    embed_ast_id_to_row_map = {v: k for k, v in embed_row_to_ast_id_map.items()}
    ast_row = embed_ast_id_to_row_map[ast_id]
    print 'printing program sequence for hoc {} and ast id {}'.format(hoc_num, ast_id)
    
    block_string_to_row_map = pickle.load(open(BLOCK_STRING_TO_BLOCK_ROW_MAP, "rb" ))
    block_row_to_string_map = {v: k for k, v in block_string_to_row_map.items()}
    ast_mat = np.load(BLOCK_MAT_PREFIX + hoc_num + BLOCK_LIMIT_TIMESTEPS +  MAT_SUFFIX)
    num_asts, max_ast_len, num_blocks = ast_mat.shape
    program = []
    for t in xrange(max_ast_len):
        block_row = np.argmax(ast_mat[ast_row,t,:])
        block_string = block_row_to_string_map[block_row]
        program.append(block_string)
    print "dimension num_blocks {}".format(num_blocks)
    print program

def convert_to_block_strings(mat_with_block_rows):
    num_samples,  num_timesteps  = mat_with_block_rows.shape
    block_string_to_row_map = pickle.load(open(BLOCK_STRING_TO_BLOCK_ROW_MAP, "rb" ))
    block_row_to_string_map = {v: k for k, v in block_string_to_row_map.items()}
    mat_with_block_strings = np.empty((num_samples, num_timesteps), dtype=object)
    for i in xrange(num_samples):
        for t in xrange(num_timesteps):
            block_string = block_row_to_string_map[int(mat_with_block_rows[i,t])]
            # print block_string
            mat_with_block_strings[i,t] = block_string
    return mat_with_block_strings




if __name__ == "__main__":
    print "You are running utils.py directly, so you must be testing it!"
    load_dataset_predict_block_all_hocs()
    # for hoc in xrange(1,10):
    #     print_sample_program(hoc_num=hoc,ast_id=0)

