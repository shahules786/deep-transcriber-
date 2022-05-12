import enum
from tkinter import N
from torch.utils.data import DataLoader,Dataset
import numpy as np
import glob 
import os 
import random



class TimitDataset(Dataset):

    def __init__(
        self,
        directory:str,
        n_speakers:int,
        n_utterances:int
    ):
        self.directory = directory
        self.n_utterances = n_utterances
        self.n_speakers = n_speakers
        self.utterances = np.random.choice(self.filter_utterances(),self.n_utterances*self.n_speakers)


    def filter_utterances(
        self,
    ):
        selected_files = []
        np_files = [file for file in glob.glob(os.path.join(self.directory,"*")) if file.endswith("npy")]
        for file in np_files:
            if np.load(file).shape[0] >= self.n_utterances:
                selected_files.append(file)

        return selected_files


    def __getitem__(
        self, 
        index
    ):

        npy_file = np.load(self.filter_utterances[index])
        utter_start = np.random.randint(0,npy_file.shape[0] - self.n_utterances)
        utterances = npy_file[utter_start:utter_start+self.n_utterances]
        
        return utterances

    def __len__(
        self,

    ):
        return len(self.filter_utterances)


def TimitCollate():

    def __init__(
        self,
        n_speakers:int,
        n_utterances:int
    ):
        self.n_speakers = n_speakers
        self.n_utterances = n_utterances


    def __call__(
        self,
        batch
    ):
        batch = batch.reshape((self.n_speakers*self.n_utterances, batch.shape(2),batch.shape(3)))
        permute = random.sample(range(0,self.n_speakers*self.n_utterances),self.n_speakers*self.n_utterances)
        unpermute = permute.copy()
        for i,j in enumerate(permute):
            unpermute[j] = i

        return {"data": batch[permute],
                "unpermute":unpermute
                }




