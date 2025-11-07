# Compute JVP coefficients from the Jones polynomial over Z[q^{1/2}, q^{-1/2}] 

from collections import defaultdict

def _poly_add(A, B):
    out = defaultdict(int)
    for d,c in A.items():
        out[d] += c
    for d,c in B.items():
        out[d] += c
    return {d:c for d,c in out.items() if c != 0}

def _poly_scalar_mul(A, k):
    if k == 0: return {}
    return {d: k*c for d,c in A.items()}

def _poly_mul_p(A):
    return {d+1: c for d,c in A.items()}

def _mul_by_x(A, B):
    # x*(A + B x) = B + (A + p B) x
    return (B, _poly_add(A, _poly_mul_p(B)))

def _mul_by_y(A, B):
    # y*(A + B x) = (x - p)*(A + B x) = (B - p A) + A x
    return (_poly_add(B, _poly_scalar_mul(_poly_mul_p(A), -1)), A)

def _power_table_x(n):
    """List [(A_0,B_0),...,(A_n,B_n)] with x^k = A_k + B_k x."""
    T = [({0:1}, {})]                  # k=0: 1
    if n == 0: return T
    A, B = {0:0}, {0:1}                # k=1: x
    T.append((A,B))
    for _ in range(2, n+1):
        A, B = _mul_by_x(A, B)
        T.append((A,B))
    return T

def _power_table_y(n):
    """List [(A_0,B_0),...,(A_n,B_n)] with y^k = A_k + B_k x, where y = x - p."""
    T = [({0:1}, {})]                  # k=0: 1
    if n == 0: return T
    A, B = {1:-1}, {0:1}               # k=1: y = -p + x
    T.append((A,B))
    for _ in range(2, n+1):
        A, B = _mul_by_y(A, B)
        T.append((A,B))
    return T

def jones_to_Vxp(coefs, *, input_q_is_half_power=False):
    """
    Convert V(q) = sum_k c_k q^k  to  V(x,p) = A(p) + B(p) x
    under the substitution  x = q^{1/2},  x - p = q^{-1/2}  (so x(x-p)=1 and x^2 = p x + 1).
    
    Parameters
    ----------
    coefs : dict[int,int]
        Map k -> c_k, meaning the term c_k * q^k.
        (Exponents k may be negative.)
    input_q_is_half_power : bool
        If False (default): your 'q' is the standard Jones variable with *integer* exponents,
        so q = x^2 and q^{-1} = (x - p)^2.  Then q^k -> x^{2k}, q^{-m} -> (x - p)^{2m}.
        If True: your 'q' already equals the *half-power* variable (i.e. q^{1/2} in tables);
        then q = x and q^{-1} = x - p.  In that case q^k -> x^k, q^{-m} -> (x - p)^m.
    """
    if not isinstance(coefs, dict):
        raise TypeError("coefs must be a dict mapping exponent k to integer coefficient c_k.")
    if len(coefs) == 0:
        return {}, {}

    max_pos = max([k for k in coefs if k >= 0] or [0])
    max_neg = max([-k for k in coefs if k < 0] or [0])

    if input_q_is_half_power:
        X = _power_table_x(max_pos)
        Y = _power_table_y(max_neg)
    else:
        X = _power_table_x(2*max_pos)
        Y = _power_table_y(2*max_neg)

    A_total, B_total = {}, {}
    for k, c in coefs.items():
        if c == 0: 
            continue
        if k >= 0:
            idx = k if input_q_is_half_power else 2*k
            A_k, B_k = X[idx]
        else:
            idx = -k if input_q_is_half_power else 2*(-k)
            A_k, B_k = Y[idx]
        if c != 1:
            A_k = _poly_scalar_mul(A_k, c)
            B_k = _poly_scalar_mul(B_k, c)
        A_total = _poly_add(A_total, A_k)
        B_total = _poly_add(B_total, B_k)
    return A_total, B_total

def _to_lists(A,B):
    degA = max(A.keys()) if A else 0
    degB = max(B.keys()) if B else 0
    n = max(degA, degB)
    a = [0]*(n+1)
    b = [0]*(n+1)
    for d,c in A.items(): a[d] = c
    for d,c in B.items(): b[d] = c
    return a,b

def _pretty(A,B):
    a,b = _to_lists(A,B)
    terms = []
    for i in range(max(len(a),len(b))):
        ai = a[i] if i < len(a) else 0
        bi = b[i] if i < len(b) else 0
        if ai == 0 and bi == 0: 
            continue
        t = []
        if ai != 0: t.append(f"({ai})")
        if bi != 0: t.append(f"({bi})·x")
        power = "" if i==0 else ("p" if i==1 else f"p^{i}")
        terms.append((" + ".join(t)) + ("" if power=="" else f"·{power}"))
    return " + ".join(terms)

# ------------------- Validations -------------------

def show_case(name, coefs, *, half_power=False):
    A,B = jones_to_Vxp(coefs, input_q_is_half_power=half_power)
    a,b = _to_lists(A,B)
    print(f"\n{name}")
    print("coefs =", coefs, "(input_q_is_half_power =", half_power, ")")
    print("A(p) =", a)
    print("B(p) =", b)
    print("V(x,p) =", _pretty(A,B))


if __name__ == '__main__':
    # 1) Unlink test the user proposed:
    #    If the input variable q is the *half-power* (so V = -q - q^{-1}), then result should be p - 2x.
    show_case("Unlink with q = half-power", {1:-1, -1:-1}, half_power=True)

    show_case("Hopf link with q = half-power", {-1:-1, -5:-1}, half_power=True)
    show_case("Mirrored Hopf link with q = half-power", {1:-1, 5:-1}, half_power=True)

    #    If the input variable q is the *integer-power* (so V = -q - q^{-1} in that variable), 
    #    then q = x^2 and q^{-1} = (x - p)^2 -> result is -x^2 - (x - p)^2 = -(2 + p^2).
    #show_case("Unlink with q = integer-power", {1:-1, -1:-1}, half_power=False)

    # 2) Trefoil 3_1: V(q) = -q^4 + q^3 + q (standard integer-power q). Expect:
    #    1 - 3p^2 - 6x p^3 - 4p^4 - 5x p^5 - p^6 - x p^7
    show_case("Trefoil 3_1", {4:-1, 3:1, 1:1}, half_power=False)

    # 3) Mirrored trefoil: V(q) = -q^{-4} + q^{-3} + q^{-1}. Expect:
    #    -p^8 + x p^7 - 6p^6 + 5x p^5 - 10p^4 + 6x p^3 - 3p^2 + 1
    show_case("Mirror trefoil", {-4:-1, -3:1, -1:1}, half_power=False)
