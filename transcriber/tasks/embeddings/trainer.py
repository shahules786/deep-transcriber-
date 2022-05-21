
from distutils.debug import DEBUG
import logging
import os
import yaml 
import torch
import numpy as np
from torch.utils.data import DataLoader
from torch.optim import Adam

from transcriber.tasks.embeddings.dataloader import TimitDataset,TimitCollate
from transcriber.tasks.embeddings.model import Embeder
from transcriber.tasks.utils import min_value_check, path_check
from transcriber.tasks.embeddings.loss import Ge2eLoss


class EmbedTrainer:

    def __init__(
        self,
        input_size:int,
        hidden_size:int,
        num_layers:int,
        embedding_dim:int,
        model_dir : str,
        logger:str = "DEBUG"
    ):
        if min_value_check(input_size,0):
            self.input_size = input_size

        if min_value_check(num_layers,0):
            self.num_layers = num_layers

        if min_value_check(hidden_size,0):
            self.hidden_size = hidden_size

        if min_value_check(embedding_dim,0):
            self.embedding_dim = embedding_dim

        self._device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

        if not os.path.exists(model_dir):
            logging.info(f"Creating {model_dir}...")
            os.mkdir(model_dir)

        if path_check(model_dir):
            self.model_dir = model_dir

        if logger in ("DEBUG","INFO"):
            logging.basicConfig(level=getattr(logging,logger))
            logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)
           
    @property
    def device(self):
        return self._device

    @device.setter
    def device(self,device):

        if device not in ("cpu","cuda"):
            raise ValueError("device should be cpu or cuda")
        else:
            if getattr(torch,device).is_available():
                self._device = torch.device(device)
            else:
                raise ValueError(f"{device} not available!")
    
    def train(
        self,
        train:str,
        test:str,
        batch_size:int,
        epochs:int,
        lr:float,
        n_speakers:int,
        n_utterances:int,

        
    ):
        if path_check(train):
            self.train = train

        if path_check(test):
            self.test = test

        if min_value_check(batch_size,0):
            self.batch_size = batch_size

        if min_value_check(epochs,0):
            self.epochs = epochs

        if min_value_check(n_speakers,0):
            self.n_speakers = n_speakers

        if min_value_check(n_utterances,0):
            self.n_utterances = n_utterances
        
        self.lr = lr


        datalaoders = self._prepare_dataloaders()
        model = Embeder(input_size=self.input_size,hidden_size=self.hidden_size,num_layers=self.num_layers,
                        embed_size=self.embedding_dim)
        optimizer = Adam(self._get_optimizer(model))
        loss_fn = Ge2eLoss(N=self.n_speakers,M=self.n_utterances)

        for epoch in range(self.epochs):
            loss = {"train":[], "valid": []}
            for batch_num,data in enumerate(datalaoders['train']):
                output = self._run_single_batch(model,optimizer,loss_fn,data,phase="train")
                loss['train'].append(output['loss'])

            for batch_num,data in enumerate(datalaoders['valid']):
                output = self._run_single_batch(model,optimizer,loss_fn,data=data,phase="valid")
                loss['valid'].append(output['loss'])
            
            logging.info(f"Train loss epoch {epoch} : {np.mean(loss['train'])}")
            logging.info(f"Valid loss epoch {epoch} : {np.mean(loss['train'])}")

        logging.info("Training Finished. Saving model..")
        torch.save(model.state_dict(),os.path.join(self.model_dir,"model.pt"))
                
    def _run_single_batch(
        self,model,optimizer,criterion,data,phase
    ):
        data["data"] = data["data"].to(self.device)

        if phase == "train":
            model.train()
            optimizer.zero_grad()
        else:
            model.eval()

        with torch.set_grad_enabled(phase == "train"):
            embeddings = model(data["data"])
            embeddings = embeddings[data["unpermute"]].reshape(self.n_speakers,self.n_utterances,self.embedding_dim)
            loss = criterion(embeddings)
            if phase == "train":
                loss.backward()
                optimizer.step()
            
        return {"embeddings":embeddings,"loss":loss.item()}
            

    def _get_optimizer(
        self,
        model
    ):
        no_decay = ['gamma','beta','bias']
        optimizer_params = [
            {"params":[n for k,n in model.named_parameters() if any([i in k for i in no_decay])],
            "weight_decay":0.0,
            "lr":self.lr},

            {"params":[n for k,n in model.named_parameters() if not any([i in k for i in no_decay])],
            "weight_decay":0.01,
            "lr":self.lr},

        ]
        return optimizer_params

    def _prepare_dataloaders(
        self,
    ):
        if self.batch_size!=self.n_speakers:
            raise ValueError("batch_size should be equal to n_speakers")

        train_dataset = TimitDataset(directory=self.train, n_utterances=self.n_utterances,
                                        n_speakers = self.n_speakers)
        collate_fn = TimitCollate(n_speakers = self.n_speakers, n_utterances=self.n_utterances)
        train_dataset = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True, collate_fn=collate_fn, drop_last=True)

        valid_dataset = TimitDataset(directory=self.train, n_utterances=self.n_utterances,
                                        n_speakers = self.n_speakers)
        valid_dataset = DataLoader(valid_dataset, batch_size=self.batch_size, shuffle=True, collate_fn=collate_fn, drop_last=True)

        return {"train":train_dataset,
                "valid":valid_dataset}

    def eval(
        self,

    ):
        ##load model from model_dir using conf from __init__
        ## accept data as input and do shape checks
        ## make prediction return embeddings
        pass


if __name__ == "__main__":

    with open('transcriber/tasks/embeddings/conf.yaml') as file:
        args = yaml.full_load(file)

    trainer = EmbedTrainer(input_size=args["model"]["input_size"],
                            hidden_size=args["model"]["hidden_size"],
                            num_layers=args["model"]["num_layers"],
                            embedding_dim=args["model"]["embedding_dim"],
                            model_dir=args["model"]["model_dir"],
                            logger=args["data"]["logger"]) 
    
    trainer.train(train=args["data"]["train"],
                test=args["data"]["test"],
                batch_size=args["training"]["batch_size"],
                epochs=args["training"]["epochs"],
                lr=args["training"]["lr"],
                n_speakers=args["training"]["n_speakers"],
                n_utterances=args["training"]["n_utterances"])





