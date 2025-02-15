import numpy as np
import pandas as pd
import networkx as nx
import pydtmc  as dtmc
import time

from networkx.algorithms import community
from functools import reduce

from blooddvh import TimeDependentMarkovChain

class CompartmentModel : 
    __slots__ = ["fin", "df", "size", "name", "total_volume", "cardiac_output", "G", "prob", "volume", "markov", "scales", "markov_weibull", "markov_weibull0"]
    def __init__(self, f_name, s_name, vol=5.3, cardiac=6.5, resolution=60):
        """
        Constructor for CompartmentModel
        vol : total blood volume (L), e.g., ICRP male 5.3 L 
        cardiac : cardiac output (L), e.g., 6.5 L/min 
        resolution : seconds to take cardiac output, 60 means 1 min, i.e., 6.5 L/min
        """
        self.fin  = { "file": f_name, "sheet" : s_name }
        self.df   = pd.read_excel(self.fin["file"], sheet_name=self.fin["sheet"], engine="openpyxl")
        self.df.fillna(0, inplace=True)
        self.size   = int(self.df.columns[0])
        self.name   = [ c for c in self.df.columns[1:self.size+1] ]
        self.volume = np.cumsum( self.df.volume[0:self.size].values)/np.sum( self.df.volume[0:self.size].values )
        self.scales = np.zeros(self.size)
        self.total_volume = vol

        # flow per sec (L/s)
        self.cardiac_output = cardiac/resolution
        
        # Create network
        self.G = nx.DiGraph()

        # 1. node
        for i, c in enumerate(self.name):
            self.G.add_node(c)
            
        # 2. edges with transition probability
        self.prob = np.array(self.df.values[0:self.size, 1:self.size+1], dtype=np.float64)
        for row in range(self.size):
            # normalize to prevent non-100
            flow_sum = sum(self.prob[row])
            # calculate probability of leaving
            for col in range(self.size):
                self.prob[row, col] *= self.cardiac_output/100.0
                self.prob[row, col] /= self.total_volume * self.df.volume[row]/100.0
            # probability of staying
            self.prob[row,row] = 1.0 - sum(self.prob[row])
            self.scales[row]   = 0.01 * self.total_volume * self.df.volume[row]
            self.scales[row]  /= (cardiac/resolution * 0.01 * self.df.flow_sum[row])

            # network edge for non-zero transition
            for col in range(self.size):
                if self.prob[row, col] > 0 :
                    self.G.add_edge(self.name[row], self.name[col], weight=self.prob[row,col])

        # 3. Markov chain
        self.markov = dtmc.MarkovChain(self.prob, self.name)

        # 4. Time dependent Markov chain using Weibull distribution
        shapes_two = 2.0 * np.ones(self.size)
        self.markov_weibull  = TimeDependentMarkovChain(self.prob, self.scales, shapes_two)

    def desc(self):
        # getting different graph attributes 
        print("Total number of nodes: ", int(self.G.number_of_nodes())) 
        print("Total number of edges: ", int(self.G.number_of_edges())) 
        print("List of all nodes: ", list(self.G.nodes())) 
        #print("List of all edges: ", list(self.G.edges())) 
        #print("In-degree for all nodes: ", dict(self.G.in_degree())) 
        #print("Out degree for all nodes: ", dict(self.G.out_degree)) 
