import sys
from pyannote.core import Annotation, Segment
from pyannote.metrics.diarization import DiarizationErrorRate
def load(p):
    a = Annotation()
    for l in open(p):
        f = l.split()
        if f and f[0] == "SPEAKER":
            s, d = float(f[3]), float(f[4]); a[Segment(s, s + d)] = f[7]
    return a
ref, hyp = load(sys.argv[1]), load(sys.argv[2])
print("hyp speakers:", len(hyp.labels()), "ref speakers:", len(ref.labels()))
for collar, skip in ((0.0, False), (0.25, False), (0.25, True)):
    d = DiarizationErrorRate(collar=collar, skip_overlap=skip)(ref, hyp, detailed=True)
    t = d["total"]
    print(f"collar {collar} skip_overlap {skip}: DER {100*d['diarization error rate']:.2f}%  "
          f"miss {100*d['missed detection']/t:.2f}  FA {100*d['false alarm']/t:.2f}  confusion {100*d['confusion']/t:.2f}")
