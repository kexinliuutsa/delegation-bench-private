"""Multi-kernel MMD/DAN-style adaptation sharing PIDR-v1's encoder."""
import math,statistics
from .pidr_v1 import PIDRV1
class MMDDelegation(PIDRV1):
 def fit_alignment(self,coding,web,epochs=8,lr=.03,lambda_align=.1,bandwidths=(.5,1,2)):
  # First-moment diagonal descent is the explicit projection update; objective diagnostics use RBF MMD.
  xc=[self.raw(x) for x in coding];xw=[self.raw(x) for x in web]
  for _ in range(epochs):
   for j in range(self.latent_dim):
    gap=sum(x[j] for x in xc)/len(xc)-sum(x[j] for x in xw)/len(xw);self.scales[j]*=math.exp(max(-.05,min(.05,-lr*lambda_align*gap*gap)))
   avg=sum(self.scales)/len(self.scales);self.scales=[max(self.target_std,min(8,x/avg)) for x in self.scales]
  return self
