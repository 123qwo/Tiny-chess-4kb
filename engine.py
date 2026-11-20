"""A deterministic 0x88 chess engine for tiny-chess-01."""
import json
import os
from urllib.request import Request, urlopen

FV = [0, 100, 320, 330, 500, 900, 0]
N, S, E, W = 16, -16, 1, -1
NE, NW, SE, SW = N+E, N+W, S+E, S+W
KNIGHT = [33, 31, 18, 14, -14, -18, -31, -33]
KING = [NE, N, NW, E, W, SE, S, SW]
BISHOP = [NE, NW, SE, SW]
ROOK = [N, E, S, W]
DIRECTIONS = ((), (), KNIGHT, BISHOP, ROOK, KING, KING)

# Original PSTs encoded at 5 cp per character; decoding runs once at startup.
def unpack_pst(text):
    return [5*(ord(c)-65) for f in range(0,64,8) for c in text[f:f+8]+'A'*8]

PST_DATA = 'AAAAAAAABCC==CCBB@?AA?@BAAAEEAAABBCFFCBBCCEGGECCKKKKKKKKAAAAAAAA79;;;;979=ABBA=9;BCDDCB;;ADEEDA;;BDEEDB;;ACDDCA;9=AAAA=979;;;;97=??????=?BAAAAB??CCCCCC??ACCCCA??BBCCBB??ABCCBA??AAAAAA?=??????=AAABBAAA@AAAAAA@@AAAAAA@@AAAAAA@@AAAAAA@@AAAAAA@BCCCCCCBAAAAAAAA=??@@??=?ABAAAA??BBBBBA?AABBBBA@@ABBBBA@?ABBBBA??AAAAAA?=??@@??=EGCAACGEEEAAAAEE?======?=;;99;;=;997799;;997799;;997799;;997799;7;;;;;;7;;AAAA;;;?EGGE?;;?GIIG?;;?GIIG?;;?EGGE?;;=?AA?=;79;==;97'
PST_P, PST_N, PST_B, PST_R, PST_Q, PST_KMG, PST_KEG = (
    unpack_pst(PST_DATA[i:i+64]) for i in range(0,448,64)
)
PSTS = [None, PST_P, PST_N, PST_B, PST_R, PST_Q, PST_KMG]
PASSED = [0,0,5,15,30,50,80,0]

def sq_of(u): return (ord(u[0])-97) + 16*(int(u[1])-1)
def mirror(s): return s ^ 112

START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
SQUARES = [16*r+f for r in range(8) for f in range(8)]
PHASE = (0, 0, 1, 1, 2, 4, 0)
MATERIAL = (0, 1, 3, 3, 5, 9, 0)
PSV = [[0]*128 for _ in range(16)]
RIGHTS = [15]*128
for i, mask in ((0,13),(4,12),(7,14),(112,7),(116,3),(119,11)):
    RIGHTS[i] = mask

# Use a bit per mailbox square so pawn masks need no index conversion.
FRONT = [[0]*128 for _ in range(2)]
for side in (0,1):
    for i in SQUARES:
        for j in SQUARES:
            if abs((i&7)-(j&7)) <= 1 and ((j>>4) > (i>>4) if not side else (j>>4) < (i>>4)):
                FRONT[side][i] |= 1<<j
    for kind in range(1,6):
        for i in SQUARES:
            PSV[kind+8*side][i] = (-1 if side else 1)*(FV[kind]+PSTS[kind][mirror(i) if side else i])

ATTACK = [None]*128
for sq in SQUARES:
    def targets(steps):
        return tuple(sq+d for d in steps if not (sq+d)&136)
    ATTACK[sq] = (targets((-15,-17)),targets((15,17)),targets(KNIGHT),
                  tuple((sq+d,d,3+(d in ROOK)) for d in KING if not (sq+d)&136))

def attacked(bd,sq,by):
    color = by<<3
    data = ATTACK[sq]
    for i in data[by]:
        if bd[i]==color+1:
            return True
    for i in data[2]:
        if bd[i]==color+2:
            return True
    for i,d,t in data[3]:
        if bd[i]==color+6:
            return True
        while not i&136:
            p = bd[i]
            if p:
                if p==color+t or p==color+5:
                    return True
                break
            i += d
    return False

class Board:

    def __init__(self, fen):
        self.bd = bytearray(128)
        self.kings = [0,0]
        self.score = self.phase = self.material = self.nonkings = 0
        self.bishops = [0,0]
        self.pawns = [0,0]
        rows, side, rights, ep, half, *_ = fen.split()
        self.side = int(side=='b')
        self.castle = sum(1<<i for i,c in enumerate('KQkq') if c in rights)
        self.ep = sq_of(ep) if ep!='-' else -1
        self.half = int(half)
        for r,row in enumerate(rows.split('/')):
            i = (7-r)*16
            for c in row:
                if c.isdigit():
                    i += int(c)
                    continue
                color = int(c.islower())
                kind = 'PNBRQK'.index(c.upper())+1
                p = kind+8*color
                self.bd[i] = p
                self.score += PSV[p][i]
                self.phase += PHASE[kind]
                self.material += (-1 if color else 1)*MATERIAL[kind]
                self.nonkings += kind!=6
                if kind==1:
                    self.pawns[color] |= 1<<i
                if kind==3:
                    self.bishops[color] += 1
                if kind==6:
                    self.kings[color] = i
                i += 1

    def checked(self):
        return attacked(self.bd,self.kings[self.side],self.side^1)

    def passed_score(self):
        key = tuple(self.pawns)
        hit = PAWNS.get(key)
        if hit is not None:
            return hit
        score = 0
        for side in (0,1):
            bb = self.pawns[side]
            enemy = self.pawns[side^1]
            while bb:
                bit = bb&-bb
                i = bit.bit_length()-1
                bb ^= bit
                if not enemy&FRONT[side][i]:
                    score += -PASSED[7-(i>>4)] if side else PASSED[i>>4]
        PAWNS[key] = score
        return score

    def evaluate(self):
        w,b = self.kings
        b ^= 112
        phase = min(self.phase,24)
        king = (PST_KMG[w]-PST_KMG[b])*phase+(PST_KEG[w]-PST_KEG[b])*(24-phase)
        score = (self.score+(king//24 if king>=0 else -(-king//24))+
                 30*((self.bishops[0]>=2)-(self.bishops[1]>=2))+self.passed_score())
        return -score if self.side else score

    def gen(self, tactical=False):
        bd, side = self.bd,self.side
        color = side<<3
        push, promotion, home = (-16,0,6) if side else (16,7,1)
        for i in SQUARES:
            p = bd[i]
            if not p or p>>3 != side:
                continue
            kind = p&7
            if kind==1:
                j = i+push
                if not j&136 and not bd[j]:
                    if j>>4==promotion:
                        for pr in (5,4,3,2):
                            yield i,j,pr,0
                    elif not tactical:
                        yield i,j,0,0
                        if i>>4==home and not bd[j+push]:
                            yield i,j+push,0,1
                for j in (i+push-1,i+push+1):
                    if j&136:
                        continue
                    v = bd[j]
                    if v and v>>3 != side:
                        if j>>4==promotion:
                            for pr in (5,4,3,2):
                                yield i,j,pr,0
                        else:
                            yield i,j,0,0
                    elif j==self.ep:
                        yield i,j,0,2
                continue
            for d in DIRECTIONS[kind]:
                j = i+d
                while not j&136:
                    v = bd[j]
                    if v:
                        if v>>3 != side:
                            yield i,j,0,0
                        break
                    if not tactical:
                        yield i,j,0,0
                    if kind in (2,6):
                        break
                    j += d
            if not tactical and kind==6 and i==4+112*side and self.castle & (3<<(2*side)):
                if not self.checked():
                    if self.castle & (1<<(2*side)) and bd[i+3]==color+4 and not (bd[i+1] or bd[i+2]) and not attacked(bd,i+1,side^1):
                        yield i,i+2,0,3
                    if self.castle & (2<<(2*side)) and bd[i-4]==color+4 and not (bd[i-1] or bd[i-2] or bd[i-3]) and not attacked(bd,i-1,side^1):
                        yield i,i-2,0,3

    def make(self, m):
        i,j,pr,flag = m
        bd,side = self.bd,self.side
        pc = bd[i]
        kind = pc&7
        cap_sq = j+16*(2*side-1) if flag==2 else j
        cap = bd[cap_sq]
        victim = cap&7
        undo = (pc,cap,self.castle,self.ep,self.half,self.score,self.phase,self.kings[side],
                *self.bishops,*self.pawns,self.material,self.nonkings)
        put = pr+8*side if pr else pc
        bd[i] = bd[cap_sq] = 0
        bd[j] = put
        self.score += PSV[put][j]-PSV[pc][i]-PSV[cap][cap_sq]
        if kind==1:
            self.pawns[side] ^= 1<<i
            if not pr:
                self.pawns[side] ^= 1<<j
        if cap:
            self.nonkings -= 1
            if victim==1:
                self.pawns[side^1] ^= 1<<cap_sq
            if victim==3:
                self.bishops[side^1] -= 1
        if pr==3:
            self.bishops[side] += 1
        if cap or pr:
            self.phase += PHASE[pr]-PHASE[victim]
            self.material += (-1 if side else 1)*(MATERIAL[victim]+(MATERIAL[pr]-1 if pr else 0))
        if kind==6:
            self.kings[side] = j
        if flag==3:
            a,z = (i+3,i+1) if j>i else (i-4,i-1)
            rook = bd[a]
            bd[a],bd[z] = 0,rook
            self.score += PSV[rook][z]-PSV[rook][a]
        self.castle &= RIGHTS[i]&RIGHTS[j]
        self.ep = (i+j)//2 if flag==1 else -1
        self.half = 0 if kind==1 or cap else self.half+1
        self.side ^= 1
        return undo

    def unmake(self, m, undo):
        i,j,_,flag = m
        (pc,cap,self.castle,self.ep,self.half,self.score,self.phase,king,
         self.bishops[0],self.bishops[1],self.pawns[0],self.pawns[1],self.material,self.nonkings) = undo
        self.side ^= 1
        side,bd = self.side,self.bd
        self.kings[side] = king
        bd[i],bd[j] = pc,cap
        if flag==2:
            bd[j],bd[j+16*(2*side-1)] = 0,cap
        if flag==3:
            a,z = (i+3,i+1) if j>i else (i-4,i-1)
            bd[a],bd[z] = bd[z],0

    def key(self):
        ep,side,bd = self.ep,self.side,self.bd
        if ep>=0:
            push = 16*(1-2*side)
            victim = ep-push
            for i in (victim-1,victim+1):
                if not i&136 and bd[i]==1+8*side:
                    bd[ep],bd[i],bd[victim] = bd[i],0,0
                    legal = not self.checked()
                    bd[i],bd[victim],bd[ep] = bd[ep],9-8*side,0
                    if legal:
                        break
            else:
                ep = -1
        return bytes(bd),side,self.castle,ep

    def decode(self, u):
        i,j = sq_of(u[:2]),sq_of(u[2:4])
        kind = self.bd[i]&7
        pr = ' pnbrq'.index(u[4]) if len(u)==5 else 0
        flag = (2 if j==self.ep else 1 if abs(i-j)==32 else 0) if kind==1 else 3 if kind==6 and abs(i-j)==2 else 0
        return i,j,pr,flag

    def legal(self, m):
        return not attacked(self.bd,self.kings[self.side^1],self.side)

    def dead(self):
        return self.nonkings==0 or (self.nonkings==1 and not any(self.pawns) and (self.phase==1))

MATE = 30000
BUDGET = 150000
TT, KILLERS, PAWNS, HISTORY = {},{},{},{}
nodes = limit = completed_depth = ply_cap = 0

class Exhausted(Exception):
    pass

def order(b, m, killer=None):
    i,j,pr,flag = m
    pc = b.bd[i]
    cap = 1 if flag==2 else b.bd[j]&7
    if cap or pr:
        return 60000+10*FV[cap]-FV[pc&7]+FV[pr]
    if m==killer:
        return 50000
    return (1-2*b.side)*(PSV[pc][j]-PSV[pc][i])

def search(b,depth,alpha,beta,ply):
    global nodes
    if nodes==limit:
        raise Exhausted
    nodes += 1
    chk = b.checked()
    key = b.key() if depth>0 or b.half>=4 else None
    seen = HISTORY.get(key,0)
    if b.dead():
        return 0
    if b.half>=100 or seen>=2 or ply>=ply_cap:
        if chk and not any_legal(b):
            return -MATE+ply
        if b.half>=100 or seen>=2 or not any_legal(b):
            return 0
        material = b.material*(1-2*b.side)
        return 20000 if material>=5 else -20000 if material<=-5 else 0
    if ply>=64:
        return b.evaluate() if any_legal(b) else -MATE+ply if chk else 0
    if key is not None:
        HISTORY[key] = seen+1
    try:
        return visit(b,depth,alpha,beta,ply,chk,None if seen else key)
    finally:
        if key is not None:
            if seen:
                HISTORY[key] = seen
            else:
                del HISTORY[key]

def any_legal(b):
    for m in b.gen():
        undo = b.make(m)
        legal = b.legal(m)
        b.unmake(m,undo)
        if legal:
            return True
    return False

def visit(b,depth,alpha,beta,ply,chk,key):
    quiet = depth<=0 and not chk
    a0 = alpha
    best = -2*MATE
    if quiet:
        best = b.evaluate()
        if best>=beta:
            return best if b.nonkings>5 or any_legal(b) else 0
        alpha = max(alpha,best)
    entry = None
    ttmove = None
    if depth>0 and key is not None:
        key = key,b.half,ply if ply_cap<75 else 0
        entry = TT.get(key)
        if entry:
            d,flag,score,ttmove = entry
            score += (ply if score<0 else -ply) if abs(score)>29000 else 0
            if d>=depth and (flag==0 or flag==1 and score>=beta or flag==2 and score<=alpha):
                return score
    killer = KILLERS.get(ply)
    legal = False
    bm = None
    for stage in range(2):
        if stage==0:
            if ttmove is None:
                continue
            todo = (ttmove,)
        else:
            todo = list(b.gen(quiet))
            if ttmove is not None:
                todo.remove(ttmove)
            todo.sort(key=lambda m:order(b,m,killer),reverse=True)
        for m in todo:
            undo = b.make(m)
            try:
                if not b.legal(m):
                    continue
                legal = True
                score = -search(b,depth-1,-beta,-alpha,ply+1)
            finally:
                b.unmake(m,undo)
            if score>best:
                best,bm = score,m
            if score>alpha:
                alpha = score
            if alpha>=beta:
                if depth>0 and not (undo[1] or m[2]):
                    KILLERS[ply] = m
                break
        if alpha>=beta:
            break
    if not legal and (not quiet or b.nonkings<=5 and not any_legal(b)):
        return -MATE+ply if chk else 0
    if depth>0 and key is not None and (not entry or entry[0]<=depth):
        flag = 1 if best>=beta else 2 if best<=a0 else 0
        score = best+((ply if best>0 else -ply) if abs(best)>29000 else 0)
        TT[key] = depth,flag,score,bm
    return best

def root(b,legal_uci,budget=BUDGET,history=(),remaining=200):
    global nodes,limit,completed_depth,ply_cap
    nodes,limit,completed_depth,ply_cap = 0,budget,0,remaining
    TT.clear(); KILLERS.clear(); PAWNS.clear(); HISTORY.clear()
    HISTORY[b.key()] = 1
    for key in history:
        HISTORY[key] = HISTORY.get(key,0)+1
    moves = {u:b.decode(u) for u in sorted(legal_uci)}
    best = max(moves,key=lambda u:order(b,moves[u]))
    if len(moves)==1:
        return best
    for depth in range(1,13):
        alpha = -2*MATE
        candidate = best
        try:
            for u in [best]+[x for x in moves if x!=best]:
                m = moves[u]
                undo = b.make(m)
                try:
                    score = -search(b,depth-1,-alpha-1,-alpha,1) if u!=best else -search(b,depth-1,-2*MATE,-alpha,1)
                    if u!=best and score>alpha:
                        score = -search(b,depth-1,-2*MATE,-alpha,1)
                finally:
                    b.unmake(m,undo)
                if score>alpha:
                    alpha,candidate = score,u
        except Exhausted:
            break
        best,completed_depth = candidate,depth
        if alpha>29000:
            break
    return best

def post(base,path,body):
    req = Request(base+path,json.dumps(body).encode(),{'Content-Type':'application/json'})
    with urlopen(req,timeout=30) as response:
        return json.load(response)

def main():
    base = os.environ['MAKEFUN_ENV_URL'].rstrip('/')
    while True:
        g = post(base,'/game',{})
        if g['status']=='done':
            return
        while g['status']=='your_move':
            old = Board(START)
            history = []
            for move in g['moves']:
                history.append(old.key())
                old.make(old.decode(move))
            m = root(Board(g['fen']),g['legal_moves'],history=history,remaining=g['max_plies']-g['plies'])
            g = post(base,'/move',{'game':g['game'],'move':m})

if __name__=='__main__':
    main()
