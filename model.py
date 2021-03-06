from __future__ import absolute_import
from __future__ import division
from __future__ import print_function 

import tensorflow as tf
import numpy as np
import os
import sys
import json
import pandas as pd
import argparse
import random
import pickle

from keras.preprocessing.text import text_to_word_sequence
from tqdm import *
from datasetBase import DatasetBase, DataObject
from datasetTrain import DatasetTrain
from datasetTest import DatasetTest
from subprocess import call

FLAGS = None

np.random.seed(0)
tf.set_random_seed(0)

n_inputs        = 4096
n_hidden        = 256
val_batch_size  = 100
n_frames        = 80
max_caption_len = 50
forget_bias_red = 1.0
forget_bias_gre = 1.0
dropout_prob    = 0.5
n_attention     = n_hidden

phases = {'train': 0, 'val': 1, 'test': 2}

special_tokens = {'<PAD>': 0, '<BOS>': 1, '<EOS>': 2, '<UNK>': 3}
max_caption_len = 50
print_num = 10

filters = '`","?!/.()'

class DatasetVal(DatasetBase):
    def __init__(self, data_dir, batch_size):
        super().__init__(data_dir, batch_size)
        self.feat_dir = self.data_dir + '/testing_data/feat/'
        self.json_filename = '/testing_label.json'
        self.corpus_dir = self.data_dir    

    def load_tokenizer(self):
        # should be put in same folder!
        with open('word_index.pkl', 'rb') as handle:
            self.word_index = pickle.load(handle)
        with open('idx_to_word.pkl', 'rb') as handle:
            self.idx_to_word = pickle.load(handle)
        with open('word_counts.pkl', 'rb') as handle:
            self.word_counts = pickle.load(handle)

        self.vocab_num = len(self.word_counts) + 4
        return self.vocab_num

    def build_val_data_obj_list(self):
        corpus_path = self.corpus_dir + self.json_filename

        data_file = pd.read_json(corpus_path)
        max_size = 0
        for i in range(0, len(data_file['caption'])):

            myid = data_file['id'][i]
            path = self.feat_dir + myid + '.npy'
            mydat = np.load(path)
            str_list = data_file['caption'][i]
           
            tmp_list = []
            cap_len_list = [] 
            for j in range(0, len(str_list)):
                seq = text_to_word_sequence(str_list[j], filters=filters, 
                    lower=True, split=" ")
                tmp_list.append(seq)
                cap_len_list.append(len(seq) + 1) # added <EOS>

            obj = DataObject(path, myid, tmp_list, cap_len_list)
            self.dat_dict[myid] = mydat
            max_size += 1
            self.data_obj_list.append(obj)

        self.data_obj_list = np.array(self.data_obj_list)
        self.batch_max_size = max_size
        print('[Validation] total data size: ' + str(max_size))

    def next_batch(self): 
        
        # 1. sequential chosen, batch_size should be <= 100
        current_index = self.batch_index
        max_size = self.batch_max_size
        if current_index + self.batch_size <= max_size:
            dat_list = self.data_obj_list[current_index:(current_index + self.batch_size)]
            self.batch_index += self.batch_size
        else:
            right = self.batch_size - (max_size - current_index)
            dat_list = np.append(self.data_obj_list[current_index:max_size], self.data_obj_list[0: right])
            self.batch_index = right
        
        img_batch = []
        cap_batch = []
        id_batch = []
        cap_len = []
        for d in dat_list:
            img_batch.append(self.dat_dict[d.myid])
            id_batch.append(d.myid)
            cap, l = self.sample_one_caption(d.caption_list, d.cap_len_list) # randomly pick one
            cap = np.array(cap)
            cap_batch.append(cap)
            cap_len.append(l)
        cap_batch = self.captions_to_padded_sequences(cap_batch)

        return np.array(img_batch), np.array(cap_batch), np.array(cap_len), np.array(id_batch)


def print_train(pred, cap_len, label, idx2word, batch_size, id_batch):
    
    i = np.random.randint(0, batch_size)
    eos_pred = max_caption_len - 1
    eos = cap_len[i] - 1
    for j in range(0, max_caption_len):
            if pred[i][j] == special_tokens['<EOS>']:
                eos_pred = j
                break
    
    pre = list( map (lambda x: idx2word[x] , pred[i][0:eos_pred])  )
    lab = list( map (lambda x: idx2word[x] , label[i][0:eos])  )
    print('\nid: ' + str(id_batch[i]) + '\nanswer: ' + str(lab) + '\nprediction: ' + str(pre) )

def print_val(pred, cap_len, label, idx2word, batch_size, id_batch):
    seq = []
    print_me = np.random.randint(batch_size, size=(1, print_num))
    for i in range(0, batch_size):
        eos_pred = max_caption_len - 1
        eos = cap_len[i] - 1
        for j in range(0, max_caption_len):
                if pred[i][j] == special_tokens['<EOS>']:
                    eos_pred = j
                    break
        myid = id_batch[i]
        pre = list( map (lambda x: idx2word[x] , pred[i][0:eos_pred])  )
        lab = list( map (lambda x: idx2word[x] , label[i][0:eos])  )
        pre_no_eos = list( map (lambda x: idx2word[x] , pred[i][0:(eos_pred)])  )
        sen = ' '.join([w for w in pre_no_eos])
        seq.append(sen)
        if i in print_me:
            print('\nid: ' + str(myid) + '\nanswer: ' + str(lab) + '\nprediction: ' + str(pre) )

    return seq

def print_test(pred, idx2word, batch_size, id_batch):
    
    seq = []
    for i in range(0, batch_size):
        eos_pred = max_caption_len - 1
        for j in range(0, max_caption_len):
                if pred[i][j] == special_tokens['<EOS>']:
                    eos_pred = j
                    break
        pre = list( map (lambda x: idx2word[x] , pred[i][0:eos_pred])  )
        print('\nid: ' + str(id_batch[i]) + '\nlen: ' + str(eos_pred) + '\nprediction: ' + str(pre))
        pre_no_eos = list( map (lambda x: idx2word[x] , pred[i][0:(eos_pred)])  )
        sen = ' '.join([w for w in pre_no_eos])
        seq.append(sen)
    return seq


class S2VT:
    def __init__(self, vocab_num = 0, 
                       with_attention = True, 
                       lr = 1e-3):

        self.vocab_num = vocab_num
        self.with_attention = with_attention
        self.learning_rate = lr
        self.saver = None

    def set_saver(self, saver):
        self.saver = saver
     
    def build_model(self, feat, captions=None, cap_len=None, sampling=None, phase=0):

        weights = {
            'W_feat': tf.Variable( tf.random_uniform([n_inputs, n_hidden], -0.1, 0.1), name='W_feat'), 
            'W_dec': tf.Variable(tf.random_uniform([n_hidden, self.vocab_num], -0.1, 0.1), name='W_dec')
        }
        biases = {
            'b_feat':  tf.Variable( tf.zeros([n_hidden]), name='b_feat'),
            'b_dec': tf.Variable(tf.zeros([self.vocab_num]), name='b_dec')
        }   
        embeddings = {
         'emb': tf.Variable(tf.random_uniform([self.vocab_num, n_hidden], -0.1, 0.1), name='emb')
        }

        if self.with_attention:
            weights['w_enc_out'] =  tf.Variable(tf.random_uniform([n_hidden, n_hidden]), 
                dtype=tf.float32, name='w_enc_out')
            weights['w_dec_state'] =  tf.Variable(tf.random_uniform([n_hidden, n_hidden]), 
                dtype=tf.float32, name='w_dec_state')
            weights['v'] = tf.Variable(tf.random_uniform([n_hidden, 1]), 
                dtype=tf.float32, name='v')

        batch_size = tf.shape(feat)[0]

        if phase != phases['test']:
            cap_mask = tf.sequence_mask(cap_len, max_caption_len, dtype=tf.float32)
     
        if phase == phases['train']: #  add noise
            noise = tf.random_uniform(tf.shape(feat), -0.1, 0.1, dtype=tf.float32)
            feat = feat + noise

        if phase == phases['train']:
            feat = tf.nn.dropout(feat, dropout_prob)

        feat = tf.reshape(feat, [-1, n_inputs])
        image_emb = tf.matmul(feat, weights['W_feat']) + biases['b_feat']
        image_emb = tf.reshape(image_emb, [-1, n_frames, n_hidden])
        image_emb = tf.transpose(image_emb, perm=[1, 0, 2])
        
        with tf.variable_scope('LSTM1'):
            lstm_red = tf.nn.rnn_cell.BasicLSTMCell(n_hidden, forget_bias=forget_bias_red, state_is_tuple=True)
            if phase == phases['train']:
                lstm_red = tf.contrib.rnn.DropoutWrapper(lstm_red, output_keep_prob=dropout_prob)    
        with tf.variable_scope('LSTM2'):
            lstm_gre = tf.nn.rnn_cell.BasicLSTMCell(n_hidden, forget_bias=forget_bias_gre, state_is_tuple=True)
            if phase == phases['train']:
                lstm_gre = tf.contrib.rnn.DropoutWrapper(lstm_gre, output_keep_prob=dropout_prob)    

        state_red = lstm_red.zero_state(batch_size, dtype=tf.float32)
        state_gre = lstm_gre.zero_state(batch_size, dtype=tf.float32)

        if self.with_attention:
            padding = tf.zeros([batch_size, n_hidden + n_attention])
        else:
            padding = tf.zeros([batch_size, n_hidden])

        h_src = []
        for i in range(0, n_frames):
            with tf.variable_scope("LSTM1"):
                output_red, state_red = lstm_red(image_emb[i,:,:], state_red)
            
            with tf.variable_scope("LSTM2"):
                output_gre, state_gre = lstm_gre(tf.concat([padding, output_red], axis=1), state_gre)
                h_src.append(output_gre) # even though padding is augmented, output_gre/state_gre's shape not change

        h_src = tf.stack(h_src, axis = 0)

        bos = tf.ones([batch_size, n_hidden])
        padding_in = tf.zeros([batch_size, n_hidden])

        logits = []
        max_prob_index = None

        if self.with_attention:
            def bahdanau_attention(time, prev_output=None):
                
                if time == 0:
                    H_t = h_src[-1,:, :] # encoder last output as first target input, H_t
                else:
                    H_t = prev_output

                H_t = tf.matmul(H_t, weights['w_dec_state'])
                H_s = tf.identity(h_src) # copy
                    
                H_s = tf.reshape(H_s, (-1, n_hidden))
                score = tf.matmul(H_s, weights['w_enc_out'])
                score = tf.reshape(score, (-1, batch_size, n_hidden))
                score = tf.add(score, tf.expand_dims(H_t, 0))
                
                score = tf.reshape(score, (-1, n_hidden))
                score = tf.matmul(tf.tanh(score), weights['v'])
                score = tf.reshape(score, (n_frames, batch_size, 1))
                score = tf.nn.softmax(score, dim=-1, name='alpha')

                H_s = tf.reshape(H_s, (-1, batch_size, n_hidden))
                C_i = tf.reduce_sum(tf.multiply(H_s, score), axis=0)
                return C_i


        cross_ent_list = []
        for i in range(0, max_caption_len):

            with tf.variable_scope("LSTM1"):
                output_red, state_red = lstm_red(padding_in, state_red)

            if i == 0:
                with tf.variable_scope("LSTM2"):
                    con = tf.concat([bos, output_red], axis=1)
                    if self.with_attention:
                        C_i = bahdanau_attention(i)
                        con = tf.concat([con, C_i], axis=1)

                    output_gre, state_gre = lstm_gre(con, state_gre)
            else:
                if phase == phases['train']:
                    if sampling[i] == True:
                        feed_in = captions[:, i - 1]
                    else:
                        feed_in = tf.argmax(logit_words, 1)
                else:
                    feed_in = tf.argmax(logit_words, 1)
                with tf.device("/cpu:0"):
                    embed_result = tf.nn.embedding_lookup(embeddings['emb'], feed_in)
                with tf.variable_scope("LSTM2"):
                    con = tf.concat([embed_result, output_red], axis=1)
                    if self.with_attention:
                        C_i = bahdanau_attention(i, state_gre[1]) # (state_c, state_h)
                        con = tf.concat([con, C_i], axis=1)
                    output_gre, state_gre = lstm_gre(con, state_gre)

            logit_words = tf.matmul(output_gre, weights['W_dec']) + biases['b_dec']
            logits.append(logit_words)

            if phase != phases['test']:
                labels = captions[:, i]
                one_hot_labels = tf.one_hot(labels, self.vocab_num, on_value = 1, off_value = None, axis = 1) 
                cross_entropy = tf.nn.softmax_cross_entropy_with_logits(logits=logit_words, labels=one_hot_labels)
                cross_entropy = cross_entropy * cap_mask[:, i]
                cross_ent_list.append(cross_entropy)
        
        loss = 0.0
        if phase != phases['test']:
            cross_entropy_tensor = tf.stack(cross_ent_list, 1)
            loss = tf.reduce_sum(cross_entropy_tensor, axis=1)
            loss = tf.divide(loss, tf.cast(cap_len, tf.float32))
            loss = tf.reduce_mean(loss, axis=0)

        logits = tf.stack(logits, axis = 0)
        logits = tf.reshape(logits, (max_caption_len, batch_size, self.vocab_num))
        logits = tf.transpose(logits, [1, 0, 2])
        
        summary = None
        if phase == phases['train']:
            summary = tf.summary.scalar('training loss', loss)
        elif phase == phases['val']:
            summary = tf.summary.scalar('validation loss', loss)

        return logits, loss, summary

    def inference(self, logits):
        
        dec_pred = tf.argmax(logits, 2)
        return dec_pred

    def optimize(self, loss_op):

        params = tf.trainable_variables()
        optimizer = tf.train.AdamOptimizer(self.learning_rate)
        gradients, variables = zip(*optimizer.compute_gradients(loss_op))
        gradients, _ = tf.clip_by_global_norm(gradients, 5.0)
        train_op = optimizer.apply_gradients(zip(gradients, params))

        return train_op

def train():
    datasetTrain = DatasetTrain(FLAGS.data_dir, FLAGS.batch_size)
    datasetTrain.build_train_data_obj_list()
    vocab_num = datasetTrain.dump_tokenizer()

    datasetVal = DatasetVal(FLAGS.data_dir, val_batch_size)
    datasetVal.build_val_data_obj_list()
    _ = datasetVal.load_tokenizer() # vocab_num are the same

    train_graph = tf.Graph()
    val_graph = tf.Graph()

    gpu_config = tf.ConfigProto()
    gpu_config.gpu_options.allow_growth = True

    with train_graph.as_default():
        feat = tf.placeholder(tf.float32, [None, n_frames, n_inputs], name='video_features')
        captions = tf.placeholder(tf.int32, [None, max_caption_len], name='captions')
        sampling = tf.placeholder(tf.bool, [max_caption_len], name='sampling')
        cap_len = tf.placeholder(tf.int32, [None], name='cap_len')
        model = S2VT(vocab_num=vocab_num, with_attention=FLAGS.with_attention, 
                    lr=FLAGS.learning_rate)
        logits, loss_op, summary = model.build_model(feat, captions, cap_len, sampling, phases['train'])
        dec_pred = model.inference(logits)
        train_op = model.optimize(loss_op)

        model.set_saver(tf.train.Saver(max_to_keep = 3))
        init = tf.global_variables_initializer()
    train_sess = tf.Session(graph=train_graph, config=gpu_config)

    with val_graph.as_default():
        feat_val = tf.placeholder(tf.float32, [None, n_frames, n_inputs], name='video_features')
        captions_val = tf.placeholder(tf.int32, [None, max_caption_len], name='captions')
        cap_len_val = tf.placeholder(tf.int32, [None], name='cap_len')

        model_val = S2VT(vocab_num=vocab_num, with_attention=FLAGS.with_attention, lr=FLAGS.learning_rate)
        logits_val, loss_op_val, summary_val = model_val.build_model(feat_val, 
                    captions_val, cap_len_val, phase=phases['val'])
        dec_pred_val = model_val.inference(logits_val)

        model_val.set_saver(tf.train.Saver(max_to_keep=3))
    val_sess = tf.Session(graph=val_graph, config=gpu_config)

    load = FLAGS.load_saver
    if not load:
        train_sess.run(init)
        print("No saver was loaded")
    else:
        saver_path = FLAGS.save_dir # load checkpoint, but the loss in tensorboard will crash!!
        latest_checkpoint = tf.train.latest_checkpoint(saver_path)
        model.saver.restore(train_sess, latest_checkpoint)
        print("Saver Loaded: " + latest_checkpoint)

    ckpts_path = FLAGS.save_dir + "save_net.ckpt"
    summary_writer = tf.summary.FileWriter(FLAGS.log_dir + '/train')
    summary_writer.add_graph(train_graph)
    summary_writer.add_graph(val_graph)

    samp_prob = np.arange(0.0, 1.0, (1.0/FLAGS.num_epoches))
    samp_prob = np.flip(samp_prob, 0)
    print("Sample Prob.:", samp_prob)
    pbar = tqdm(range(0, FLAGS.num_epoches))

    for epo in pbar:
        datasetTrain.shuffle_perm()
        num_steps = int( datasetTrain.batch_max_size / FLAGS.batch_size )
        epo_loss = 0
        for i in range(0, num_steps):
            data_batch, label_batch, caption_lens_batch, id_batch = datasetTrain.next_batch()
            samp = datasetTrain.schedule_sampling(samp_prob[epo], caption_lens_batch)
            if i % FLAGS.num_display_steps == 1:
                # training 
                run_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
                _, loss, p, summ = train_sess.run([train_op, loss_op, dec_pred, summary], 
                                feed_dict={feat: data_batch,
                                           captions: label_batch,
                                           cap_len: caption_lens_batch,
                                           sampling: samp},
                                options=run_options)
                summary_writer.add_summary(summ, global_step=(epo * num_steps) + i)
                print("\n[Train. Prediction] Epoch " + str(epo) + ", step " \
                        + str(i) + "/" + str(num_steps) )
                print_train(p, caption_lens_batch, label_batch, 
                    datasetTrain.idx_to_word, FLAGS.batch_size, id_batch)

            else:
                _, loss, p = train_sess.run([train_op, loss_op, dec_pred], 
                                feed_dict={feat: data_batch,
                                           captions: label_batch,
                                           cap_len: caption_lens_batch,
                                           sampling: samp})

            epo_loss += loss
            print("Epoch " + str(epo) + ", step " + str(i) + "/" + str(num_steps) + \
                ", (Training Loss: " + "{:.4f}".format(loss)+")")

        print("\n[FINISHED] Epoch " + str(epo) + \
                ", (Training Loss (per epoch): " + "{:.4f}".format(epo_loss) + ")") 

        if epo % FLAGS.num_saver_epoches == 0:
            ckpt_path = model.saver.save(train_sess, ckpts_path, 
                global_step=(epo * num_steps) + num_steps - 1)
            print("\nSaver saved: " + ckpt_path)
            
            # validation
            model_val.saver.restore(val_sess, ckpt_path)
            print("\n[Val. Prediction] Epoch " + str(epo) + ", step " + str(num_steps) + "/" \
                + str(num_steps) )
            
            num_steps_val = int( datasetVal.batch_max_size / val_batch_size )
            total_loss_val = 0 
            txt = open(FLAGS.output_filename, 'w')
            for j in range(0, num_steps_val):

                data_batch, label_batch, caption_lens_batch, id_batch = datasetVal.next_batch()
                loss_val, p_val, summ = val_sess.run([loss_op_val, dec_pred_val, summary_val], 
                                        feed_dict={feat_val: data_batch,
                                                   captions_val: label_batch,
                                                   cap_len_val: caption_lens_batch})
                seq = print_val(p_val, caption_lens_batch, 
                    label_batch, datasetVal.idx_to_word, val_batch_size, id_batch)
            
                total_loss_val += loss_val
                summary_writer.add_summary(summ, global_step=(epo * num_steps_val) + j)
                
                for k in range(0, val_batch_size):
                    txt.write(id_batch[k] + "," + seq[k] + "\n")
            
            print('\nSave file: ' + FLAGS.output_filename)
            txt.close()
            call(['python', 'bleu_eval.py', FLAGS.output_filename])

            print("Validation: " + str((j+1) * val_batch_size) + "/" + \
                    str(datasetVal.batch_max_size) + ", done..." \
                    + "Total Loss: " + "{:.4f}".format(total_loss_val))
    
    print('\n\nTraining finished!')

def test():
    datasetTest = DatasetTest(FLAGS.data_dir, FLAGS.test_dir, FLAGS.batch_size)
    datasetTest.build_test_data_obj_list()
    vocab_num = datasetTest.load_tokenizer()

    test_graph = tf.Graph()
    gpu_config = tf.ConfigProto()
    gpu_config.gpu_options.allow_growth = True

    with test_graph.as_default():
        feat = tf.placeholder(tf.float32, [None, n_frames, n_inputs], name='video_features')
        model = S2VT(vocab_num=vocab_num, with_attention=FLAGS.with_attention)
        logits, _, _ = model.build_model(feat, phase=phases['test'])
        dec_pred = model.inference(logits)

        model.set_saver(tf.train.Saver(max_to_keep=3))
    sess = tf.Session(graph=test_graph, config=gpu_config)

    saver_path = FLAGS.save_dir
    print('saver path: ' + saver_path)
    latest_checkpoint = tf.train.latest_checkpoint(saver_path)
    
    model.saver.restore(sess, latest_checkpoint)
    print("Saver Loaded: " + latest_checkpoint)

    txt = open(FLAGS.output_filename, 'w')

    num_steps = int( datasetTest.batch_max_size / FLAGS.batch_size)
    for i in range(0, num_steps):

        data_batch, id_batch = datasetTest.next_batch()
        p = sess.run(dec_pred, feed_dict={feat: data_batch})
        seq = print_test(p, datasetTest.idx_to_word, FLAGS.batch_size, id_batch)

        for j in range(0, FLAGS.batch_size):
            txt.write(id_batch[j] + "," + seq[j] + "\n")

        print("Inference: " + str((i+1) * FLAGS.batch_size) + "/" + \
                str(datasetTest.batch_max_size) + ", done..." )
    
    print('\n\nTesting finished.')
    print('\n Save file: ' + FLAGS.output_filename)
    txt.close()

def main(_):

  if FLAGS.test_mode == False: # training
    if FLAGS.load_saver == True:
      print('load saver!!')
    else:
      print('not load saver, init')

    # whether load saver or not, reinitialized the log dir
    if tf.gfile.Exists(FLAGS.log_dir):
      tf.gfile.DeleteRecursively(FLAGS.log_dir)
    tf.gfile.MakeDirs(FLAGS.log_dir)
    train()
  else:
    if FLAGS.load_saver == True:
      print('load saver!!')
    else:
      print('ERROR: you cannot run test without saver...')
      exit(0)
    print('test mode: start')
    # pick from 1 of 2
    test()

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-lr', '--learning_rate', type=float, default=1e-3)
    parser.add_argument('-e', '--num_epoches', type=int, default=30)
    parser.add_argument('-b', '--batch_size', type=int, default=250)
    parser.add_argument('-t', '--test_mode', type=int, default=0)
    parser.add_argument('-d', '--num_display_steps', type=int, default=15)
    parser.add_argument('-ns', '--num_saver_epoches', type=int, default=1)
    parser.add_argument('-s', '--save_dir', type=str, default='save/')    
    parser.add_argument('-l', '--log_dir', type=str, default='logs/')
    parser.add_argument('-o', '--output_filename', type=str, default='output.txt')
    parser.add_argument('-lo', '--load_saver', type=bool, default=False)
    parser.add_argument('-at', '--with_attention', type=int, default=1)
    parser.add_argument('--data_dir', type=str, 
        default=('C:/Users/dave8/Desktop/seq2seq/MLDS_hw2_1_data')
    )
    parser.add_argument('--test_dir', type=str, 
        default=('C:/Users/dave8/Desktop/seq2seq/MLDS_hw2_1_data/testing_data')
    )

    FLAGS, unparsed = parser.parse_known_args()
    
    tf.app.run(main=main, argv=[sys.argv[0]] + unparsed)
