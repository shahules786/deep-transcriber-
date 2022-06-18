from torch import nn
from torch.nn.functional import conv1d
import torch
import logging
import numpy as np

from transcriber.tasks.utils import hertz_to_mel, mel_to_hertz

class SincConv(nn.Module):

    def __init__(
        self,
        out_channels:int,
        inp_channels:int,
        kernel_size:int,
        stride:int,
        padding:int=0,
        dilation:int=1,
        freq_low:int=30,
        min_bandwidth_freq:int=50,
        sampling_rate:int=16000
    ):

        super(SincConv,self).__init__()

        if inp_channels!=1:
            raise ValueError("sincnet only supports mono channel")
        self.inp_channels = inp_channels
        self.out_channels = out_channels

        if  kernel_size%2==0:
            logging.warn("Kernel size must be odd")
            kernel_size+1
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        self.dilation = dilation
        self.sampling_rate = sampling_rate
        self.freq_low = freq_low
        self.min_bandwidth_freq = min_bandwidth_freq

        low_freq_hertz = 30
        max_freq_hertz = self.sampling_rate/2 - (self.freq_low + self.min_bandwidth_freq)
        bandwidth_mel = np.linspace(hertz_to_mel(low_freq_hertz),
                                    hertz_to_mel(max_freq_hertz),
                                    self.out_channels+1)
        bandwidth_hertz = mel_to_hertz(bandwidth_mel)

        self.lower_freq_hertz = nn.parameter.Parameter(torch.tensor(bandwidth_hertz[:-1])).reshape(-1,1)
        self.bandwidth_hertz = nn.parameter.Parameter(torch.tensor(np.diff(bandwidth_hertz))).reshape(-1,1)

        N = torch.linspace(0,(self.kernel_size/2)-1,self.kernel_size//2)
        self.hanning_window = 0.54 - 0.46*torch.cos(2*torch.pi*N/self.kernel_size)
        self.two_pi_n = 2*torch.pi*torch.linspace(-1*self.kernel_size//2,0)/self.sampling_rate


    def forward(
        self,
        sample
    ):
        self.two_pi_n = self.two_pi_n.to(sample.device)
        self.hanning_window = self.hanning_window.to(sample.device)

        f1_cutoff_freq = self.freq_low + torch.abs(self.lower_freq_hertz)
        f2_cutoff_freq = torch.clamp(f1_cutoff_freq+self.min_bandwidth_freq+torch.abs(self.bandwidth_hertz),
                                        self.freq_low,self.sampling_rate/2)
        
        f1_cutoff_freq = torch.matmul(f1_cutoff_freq,self.two_pi_n)
        f2_cutoff_freq = torch.matmul(f2_cutoff_freq,self.two_pi_n)

        band_pass_left = (torch.sin(f2_cutoff_freq) - torch.sin(f1_cutoff_freq))/(self.two_pi_n//2)

        band_pass = torch.cat([band_pass_left*self.hanning_window,
                                (f2_cutoff_freq-f1_cutoff_freq)[:,0],
                                   torch.flip(band_pass_left*self.hanning_window,dims=[1])
                                   ]) / (2*(f2_cutoff_freq-f1_cutoff_freq).unsqueeze(1))
        
        self.filters = band_pass.reshape(self.out_channels,1,self.kernel_size)
        
        return conv1d(sample,self.filters,padding=self.padding,
                        stride=self.stride,dilation=self.dilation,
                        bias=None)

