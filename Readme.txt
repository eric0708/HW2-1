tensorflow:1.10.0
numpy:1.14.3
pandas:0.23.0
argparse:1.4.0
pickle
tqdm:4.28.1

Download the trained model from https://drive.google.com/file/d/1wFTUm3QEaY4mCTSZ02x18vHEQ4yNF4yd/view?fbclid=IwAR2BXusGeYclpDmU3RtFrCA0KVBIQFvsuuvLHlYwsxLLgTinZBbHrCsShVY in save file.
Change load_saver in the bottom of model.py to True to load trained model.


Change the directory of data_dir and test_dir in the bottom of model.py
to your .../MLDS_hw2_1_data folder and .../MLDS_hw2_1_data/testing_data folder.
Change the directory of path in bleu_eval to ".../MLDS_hw2_1_data/testing_label.json".
Then you can python model.py to get output of test data in output.txt and
bleu score of each epoch in plot_bleu.txt