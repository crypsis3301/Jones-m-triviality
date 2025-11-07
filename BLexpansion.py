from fractions import Fraction
from math import factorial
from typing import Dict, List, Tuple, Union

CoefKey = Union[int, str, Fraction]  # exponent key can be int, str-int (from JSON), or Fraction

def _as_fraction_exponent(key: CoefKey, exponent_den: int) -> Fraction:
    """Normalize a term's exponent to a Fraction r.
       - int or str k -> r = k / exponent_den
       - Fraction key -> r = key  (exponent_den ignored for that term)
    """
    if isinstance(key, Fraction):
        return key
    if isinstance(key, int):
        return Fraction(key, exponent_den)
    return Fraction(int(key), exponent_den)  # strings from JSON

def taylor_from_jones(coefs: Dict[CoefKey, int], n: int, *, exponent_den: int = 1) -> List[Fraction]:
    """
    Return [a_0, ..., a_n] where V(e^h) = sum_{m=0}^n a_m h^m + O(h^{n+1}).

    Parameters
    ----------
    coefs : dict
        Map exponent -> coefficient for V(q) = sum_k c_k q^k.
        Exponent keys may be ints/str-ints (common) or Fraction (if you already have rationals).
    n : int
        Highest power of h to compute (inclusive).
    exponent_den : int, default 1
        If your polynomial is written in powers of q^(1/2), pass exponent_den=2 and
        give integer keys j meaning the actual exponent is j/2.

    Example:
      # integer-power q
      coefs = {4:-1, 3:1, 1:1}  # V(q) = -q^4 + q^3 + q
      a = taylor_from_jones(coefs, 6)  # -> [1, 0, -3, -6, -29/4, -13/2, -187/40]

      # half-power input (q^{1/2})
      coefs_half = {8:-1, 6:1, 2:1}  # same trefoil in q^{1/2}
      a = taylor_from_jones(coefs_half, 6, exponent_den=2)
    """
    if n < 0:
        raise ValueError("n must be >= 0")

    # normalize to (r, c) pairs with r a Fraction exponent
    terms: List[Tuple[Fraction, int]] = []
    for k, c in coefs.items():
        if c == 0:
            continue
        r = _as_fraction_exponent(k, exponent_den)
        terms.append((r, int(c)))

    # power sums M_m = sum c * r^m, m=0..n
    M: List[Fraction] = [Fraction(0, 1) for _ in range(n + 1)]
    for r, c in terms:
        rp = Fraction(1, 1)   # r^0
        for m in range(n + 1):
            M[m] += c * rp
            rp *= r

    # Taylor coefficients a_m = M_m / m!
    return [M[m] / factorial(m) for m in range(n + 1)]



if __name__ == '__main__':
    
    import json

    jones_coeffs = lambda knot: {int(e): int(q) for e,q in data['data'][knot]['coeffs'].items()} 
    Jm = lambda c: [k for k,i in enumerate(c[1:]) if i != Fraction(0,1)][0]+1

    with open("jones_14_to_16.json","r") as file:
        data = json.load(file)

    knots = data['data']
    bl = taylor_from_jones(jones_coeffs('16a_hyp_jones:8741'),11)
    #print(bl)
    print(Jm(bl))