"""Dependency-light Deep-CORAL adaptation sharing PIDR-v1's encoder."""
import math
from .pidr_v1 import PIDRV1
class DeepCORALDelegation(PIDRV1):
 def fit_alignment(self,coding,web,epochs=8,lr=.03,lambda_align=.1,temporal_pairs=()):
  # Diagonal covariance alignment; no post-exposure samples or labels.
  for _ in range(epochs):
   xc=[self.raw(x) for x in coding];xw=[self.raw(x) for x in web]
   for j in range(self.latent_dim):
    vc=sum((x[j]-sum(y[j] for y in xc)/len(xc))**2 for x in xc)/max(1,len(xc)-1);vw=sum((x[j]-sum(y[j] for y in xw)/len(xw))**2 for x in xw)/max(1,len(xw)-1);self.scales[j]*=math.exp(max(-.05,min(.05,-lr*lambda_align*(vc-vw)**2/(4*self.latent_dim**2))))
   avg=sum(self.scales)/len(self.scales);self.scales=[max(self.target_std,min(8,x/avg)) for x in self.scales]
  return self
