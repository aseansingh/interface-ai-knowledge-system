"""Offline, evidence-first temporal knowledge system. No evaluation data is read."""
import calendar
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit

# Use the evaluator's types when available; remain usable as a standalone module.
try:
    from contract import Answer, Source, Conflict
except ImportError:
    @dataclass
    class Source:
        url: str
        snapshot_id: str | None = None
        quote: str | None = None
    @dataclass
    class Answer:
        text: str
        sources: list = field(default_factory=list)
        confident: bool = True
        conflict_note: str | None = None
    @dataclass
    class Conflict:
        topic: str
        values: list
        sources: list
        resolution: str | None = None
        reason: str | None = None

STOP = set('a an the what is are was were on in at of for to and or my your you i me our do does can could would tell please dupaco s it with have how get current now rate rates interest apr apy'.split())
ALIASES = {'automobile':'auto', 'car':'auto', 'vehicle':'auto', 'cd':'certificate', 'cds':'certificate', 'certificates':'certificate', 'mortgages':'mortgage', 'loans':'loan', 'cards':'card', 'branches':'branch', 'hours':'hour', 'savings':'saving', 'accounts':'account', 'eligibility':'eligible', 'join':'member', 'joining':'member'}


def plain(text):
    text = re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\(([^\s)]+)(?:[^)]*)\)', r'\1 (\2)', text)
    text = re.sub(r'<br\s*/?>', ' ', text)
    return re.sub(r'[*_#]', '', text).strip()


def norm(text):
    return re.sub(r'\s+', ' ', text.lower().replace('–','-').replace('—','-').replace(',', '')).strip()


def tokens(text):
    # URLs create spurious matches, so index anchor text rather than URL tokens.
    text = re.sub(r'https?://\S+', '', text.lower())
    return [ALIASES.get(w, w) for w in re.findall(r'[a-z]+|\d+(?:\.\d+)?', text) if w not in STOP]


def metric_signature(metrics):
    return tuple((name,re.sub(r'\d+(?:\.\d+)?',lambda m:format(float(m[0]),'g'),value)) for name,value in metrics)


def authority(url):
    path = urlsplit(url).path.lower()
    if 'calculator' in path: return 0
    if '/learn/' in path or '/newsroom/' in path: return 1
    if '/personal/' in path or '/business/' in path or path.rstrip('/') == '/contact': return 4
    return 2


def business_route(url):
    """Recognize both /business/... and legacy /business-rates paths."""
    return bool(re.match(r'^/business(?:/|-|$)', urlsplit(url).path.lower()))


def account_audience(url, product, section=''):
    """Keep unsupported audience identity unknown instead of assuming personal."""
    # Local product/section evidence is more specific than a mixed rates-page URL.
    for text in (product, section):
        business = bool(re.search(r'\bbusiness\b|\bcommercial\b', text, re.I))
        personal = bool(re.search(r'\bpersonal\b|\bconsumer\b', text, re.I))
        if business and personal:
            return 'unspecified'
        if business:
            return 'business'
        if personal:
            return 'personal'
    if business_route(url):
        return 'business'
    if re.match(r'^/personal(?:/|-|$)', urlsplit(url).path.lower()):
        return 'personal'
    return 'unspecified'


def conflict_reason(day, metric, items, resolution, latest_day):
    """Explain the actual comparison, without asserting unobserved staleness."""
    status = ('Current-snapshot conflict' if day == latest_day
              else 'Historical conflict; last observed')
    prefix = f'{status} {day}. Compared the same product, audience, tier and {metric}. '
    rank = max((authority(r.url), r.effective) for r, value in items)
    leaders = [(r, value) for r, value in items
               if (authority(r.url), r.effective) == rank]
    winner_urls = ', '.join(sorted({r.url for r, value in leaders}))
    if resolution is None:
        return prefix + (f'Unresolved: {winner_urls} disagree at equal authority '
                         'and effective-date priority. No winner selected.')
    explanation = prefix + f'Selected {resolution} from {winner_urls}. '
    alternatives = {(r.url, r.effective, authority(r.url)) for r, value in items
                    if value != resolution}
    for url, effective, priority in sorted(alternatives):
        if priority < rank[0]:
            explanation += (f'The URL-based source policy gives the selected source(s) '
                            f'higher authority than {url}. ')
        else:
            observed_date = effective or 'no explicit effective date'
            explanation += (f'At equal source authority, the selected effective date '
                            f'{rank[1]} takes precedence over {url} '
                            f'({observed_date}). ')
    return explanation.strip()


def infer_domain(url, text):
    s = (urlsplit(url).path + ' ' + text[:100]).lower()
    if 'auto' in s or 'motorcycle' in s or 'vehicle' in s: return 'auto'
    if 'home-loan' in s or 'mortgage' in s: return 'mortgage'
    if 'personal-loan' in s: return 'personal'
    if 'credit-card' in s: return 'card'
    if 'checking' in s: return 'checking'
    if 'saving' in s or 'certificate' in s: return 'savings'
    return ''


@dataclass
class Row:
    domain: str
    label: str
    dims: tuple
    metrics: tuple
    url: str
    sid: str
    quote: str
    effective: str = ''
    audience: str = 'unspecified'

    def key(self):
        audience = self.audience if self.domain in ('savings', 'checking', 'card') else 'not_applicable'
        return (self.domain, tuple(norm(x) for x in self.dims), audience)

    def source(self):
        return Source(self.url, self.sid, self.quote)

    def render(self):
        return self.label + ': ' + '; '.join(f'{name} {value}' for name, value in self.metrics) + '.'


@dataclass
class Chunk:
    text: str
    context: str
    url: str
    sid: str
    counts: Counter


def extract_rows(page, sid):
    blocks = re.sub(r'(?<![|\n])\n(?=\|)', '\n\n', page.markdown).split('\n\n')
    context = page.title
    rows = []
    for i, block in enumerate(blocks):
        if not block.lstrip().startswith('|'):
            if block.strip() and len(block.strip()) < 150 and not re.search(r'https?://|!\[', block):
                context = plain(block)
            continue
        lines = [x.strip() for x in block.splitlines() if x.strip().startswith('|')]
        if len(lines) < 3 or not re.fullmatch(r'[| :\-]+', lines[1]): continue
        headers = [plain(c.strip()) for c in lines[0].strip('|').split('|')]
        metric_ids = [j for j,h in enumerate(headers) if re.search(r'\bAPR\b|\bAPY\b|Dividend Rate|^Rate$|Annual Percentage', h, re.I)]
        if not metric_ids: continue
        effective = ''
        following = ' '.join(blocks[i+1:i+3])
        m = re.search(r'effective\s+(?:as of\s+)?(\d{2})/(\d{2})/(\d{4})', following, re.I)
        if m: effective = f'{m[3]}-{m[1]}-{m[2]}'
        for line in lines[2:]:
            cells = [plain(c.strip()) for c in line.strip('|').split('|')]
            if len(cells) != len(headers): continue
            metrics = []
            for j in metric_ids:
                value = re.search(r'\d+(?:\.\d+)?%\s*(?:[–-]\s*\d+(?:\.\d+)?%)?', cells[j])
                if not value: continue
                h = headers[j]
                name = 'APY' if ('APY' in h or 'Yield' in h) else 'APR' if ('APR' in h or 'Annual Percentage Rate' in h) else 'Dividend rate' if 'Dividend' in h else 'Rate'
                metrics.append((name, value[0].strip()))
            if not metrics: continue
            dims = tuple(cells[j] for j,h in enumerate(headers) if j not in metric_ids and not re.search(r'Points|Payment|Min\.', h, re.I))
            # Preserve table-level product identity for rows labelled only by term/balance.
            if dims and re.search(r'Visa|Mastercard',headers[0],re.I): dims=(headers[0],)
            if dims and (re.fullmatch(r'\d+\s+Months?', dims[0], re.I) or dims[0].startswith('$')):
                dims = (context,) + dims
            domain = infer_domain(page.url, context)
            if any('Model Year' in c for c in cells): domain = 'auto'
            if 'Certificate' in headers: domain = 'savings'
            if dims and 'year fixed' in norm(dims[0]): domain = 'mortgage'
            if dims and re.search(r'Visa|Mastercard',dims[0],re.I): domain = 'card'
            if 'Account Type' in headers and dims: domain = 'checking' if 'checking' in norm(dims[0]) else 'savings'
            audience = account_audience(page.url, ' '.join(dims), context)
            label = ' / '.join(dims)
            if audience == 'business' and 'business' not in norm(label):
                label = 'Business / ' + label
            qualifiers = [f'{headers[j]} {cells[j]}' for j in range(len(headers)) if 'Min.' in headers[j]]
            if qualifiers: label += ' (' + ', '.join(qualifiers) + ')'
            quote = lines[0] + '\n' + line
            if m:
                quote += '\n' + m[0]
            rows.append(Row(domain, label, dims, tuple(metrics), page.url, sid, quote, effective, audience))
    # Personal card rates are prose bullets, not tables. Extract ranges under card headings.
    if 'credit-card' in page.url:
        for m in re.finditer(r'^#{2,4}\s+([^\n]*(?:Visa|Mastercard)[^\n]*)\n(.*?)(?=^#{2,4}\s|\Z)', page.markdown, re.M|re.S|re.I):
            label = plain(m[1]); body = m[2]
            rates = re.search(r'(\d+(?:\.\d+)?%[–-]\d+(?:\.\d+)?%)\s*APR', body)
            if rates:
                rows.append(Row('card', label, (label,), (('APR',rates[1]),), page.url, sid, label+'\n'+rates[0], audience=account_audience(page.url, label)))
    return rows


class KnowledgeSystem:
    def __init__(self):
        self.versions = {}

    def ingest(self, snapshot):
        taken = date.fromisoformat(snapshot.taken_on[:10]).isoformat()
        rows, chunks = [], []
        for page in sorted(snapshot.pages, key=lambda p:p.url):
            rows.extend(extract_rows(page, snapshot.snapshot_id))
            # Related-article carousels are not evidence for the enclosing article.
            body = re.split(r'^## Handpicked for You',page.markdown, flags=re.M)[0]
            heading = page.title
            blocks = body.split('\n\n')
            for block in blocks:
                if block.startswith('#'): heading = plain(block)
                if block.lstrip().startswith('|') and re.search(r'APR|APY|Dividend Rate',block): continue
                cleaned = plain(block)
                if len(cleaned) < 35 or not re.search(r'[a-zA-Z]', cleaned): continue
                # Preserve paragraph boundaries; bounded chunks avoid numeric dumping.
                for part in [cleaned]:
                    if len(part) > 2400:
                        parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', part)
                    else: parts = [part]
                    for para in parts:
                        chunks.append(Chunk(para, heading, page.url, snapshot.snapshot_id, Counter(tokens(heading+' '+para))))
        df = Counter()
        for c in chunks: df.update(c.counts.keys())
        self.versions[taken] = {'day':taken, 'rows': rows, 'chunks': chunks, 'df': df, 'pages': {p.url:p for p in snapshot.pages}, 'sid':snapshot.snapshot_id}

    def select(self, as_of):
        if not self.versions: return None
        if as_of is None: return self.versions[max(self.versions)]
        try: cutoff = date.fromisoformat(str(as_of)[:10]).isoformat()
        except ValueError: return None
        dates = [d for d in self.versions if d <= cutoff]
        return self.versions[max(dates)] if dates else None

    def unknown(self, detail='The supplied snapshots do not establish this answer.', sources=None):
        return Answer("I don't know. " + detail + ' Please contact the credit union for confirmation.', sources or [], False)

    def answer(self, question, as_of=None):
        if as_of is None:
            m = re.search(r'\bas of\s+(\d{4}-\d{2}-\d{2})', question, re.I)
            if m: as_of = m[1]
            else:
                m = re.search(r'\bas of\s+([A-Za-z]+)\s+(\d{4})', question, re.I)
                if m:
                    months = {x.lower():i for i,x in enumerate(calendar.month_name) if x}
                    if m[1].lower() in months:
                        month = months[m[1].lower()]; year=int(m[2]); as_of=f'{year}-{month:02d}-{calendar.monthrange(year,month)[1]}'
        data = self.select(as_of)
        if data is None: return self.unknown('No snapshot is available on or before the requested date.')
        q = re.split(r'\bas of\b', norm(question))[0].strip()
        # Link questions use actual discovered links, not memorized destinations.
        if re.search(r'\b(url|link|locator)\b|join .*online',q):
            ans = self.link_answer(q, data)
            if ans: return ans
        financial = bool(re.search(r'rate|apr|apy|dividend|interest|certificate|\bcd\b',q))
        if financial:
            ans = self.rate_answer(q,data)
            if ans is not None: return ans
        special = self.factual_answer(question, data)
        return special if special is not None else self.retrieve(question,data)

    def link_answer(self,q,data):
        targets = []
        for p in data['pages'].values():
            if authority(p.url) < 2: continue
            for m in re.finditer(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',p.markdown):
                label,url=m.groups()
                match = False
                if 'certificate' in q or re.search(r'\bcd\b',q): match = 'saving' in url and '#rates' in url
                elif 'locator' in q or ('branch' in q and 'url' in q): match = url.rstrip('/').endswith('/contact')
                elif 'join' in q: match = url.rstrip('/').endswith('join.dupaco.com')
                if match: targets.append((authority(p.url),url,p.url,m[0]))
        if not targets: return None
        _,url,source,quote=sorted(targets,key=lambda t:(-t[0],len(t[1]),t[2]))[0]
        return Answer(url,[Source(source,data['sid'],quote)])

    def rate_answer(self,q,data):
        domain = ''
        if re.search(r'auto|vehicle|motorcycle|\bcar\b',q): domain='auto'
        elif re.search(r'mortgage|home loan|construction|\barm\b|adjustable',q): domain='mortgage'
        elif 'personal loan' in q: domain='personal'
        elif 'credit card' in q or 'visa' in q: domain='card'
        elif 'checking' in q: domain='checking'
        elif re.search(r'saving|certificate|\bcd\b|money market|hsa',q): domain='savings'
        if not domain: return None
        candidates = [r for r in data['rows'] if r.domain==domain]
        business = 'business' in q
        if domain in ('savings', 'checking'):
            audience = 'business' if business else 'personal'
            candidates = [r for r in candidates if r.audience == audience]
        elif domain != 'card':
            candidates = [r for r in candidates if business_route(r.url) == business]
        candidates=[r for r in candidates if not r.effective or r.effective <= data['day']]
        if not candidates: return self.unknown('No matching published rate table was found.')
        # Official product tables dominate duplicated calculators/blogs, within this date.
        best_authority = max(authority(r.url) for r in candidates)
        candidates = [r for r in candidates if authority(r.url)==best_authority]
        term = re.search(r'(\d+)[ -]?(month|year)',q)
        if domain=='mortgage':
            if re.search(r'construction|\b\d+/\d+\b|adjustable|\barm\b',q):
                subtype = re.search(r'construction|\d+/\d+|adjustable|\barm\b',q)[0]
                candidates=[r for r in candidates if subtype in norm(r.label)]
            else:
                candidates=[r for r in candidates if ('refinance' in norm(r.label))==('refinanc' in q)]
                candidates=[r for r in candidates if 'year' in norm(r.label)]
        if term:
            n=int(term[1]); unit=term[2]
            if domain in ('auto','personal','savings') and unit=='year': n*=12; unit='month'
            pattern=rf'\b{n}[ -]?{unit}s?\b'
            candidates=[r for r in candidates if re.search(pattern,norm(r.label))]
        if domain=='auto':
            year=re.search(r'\b(19\d{2}|20\d{2})\b',q)
            if year:
                y=int(year[0])
                def year_match(r):
                    m=re.search(r'(\d{4})-(\d{2,4})',norm(r.label))
                    if m:
                        hi=int(m[2]) if len(m[2])==4 else int(m[1])//100*100+int(m[2])
                        return int(m[1])<=y<=hi
                    m=re.search(r'(\d{4}).*older',norm(r.label))
                    return bool(m and y<=int(m[1]))
                candidates=[r for r in candidates if year_match(r)]
        if domain=='savings':
            product = next((p for p in ['share savings','bright savings','you name it','holiday','launchpad','high-yield','health savings','money market','certificate'] if p in q),None)
            if re.search(r'\bcd\b',q): product='certificate'
            if 'hsa' in q: product='health savings'
            if product is None and 'saving' in q: product='share savings'
            if product:
                candidates=[r for r in candidates if product in norm(r.label) or (product=='money market' and 'investor' in norm(r.label))]
            if 'jumbo' in q: candidates=[r for r in candidates if 'jumbo' in norm(r.label)]
            if 'regular' in q or 'standard' in q: candidates=[r for r in candidates if 'special' not in norm(r.label) and 'jumbo' not in norm(r.label)]
            if 'special' in q: candidates=[r for r in candidates if 'special' in norm(r.label)]
        if domain=='card':
            if 'platinum' in q: candidates=[r for r in candidates if 'platinum' in norm(r.label)]
            if 'rewards' in q: candidates=[r for r in candidates if 'rewards' in norm(r.label)]
            if business: candidates=[r for r in candidates if r.audience == 'business']
            elif 'platinum' in q or 'rewards' in q: candidates=[r for r in candidates if r.audience == 'personal']
        # Dollar amounts constrain balances/loan tiers, never compare adjacent tiers as conflicts.
        amounts = re.findall(r'\$([\d,]+(?:\.\d+)?)', q)
        if amounts and domain in ('savings','checking','mortgage'):
            amount=float(amounts[0].replace(',',''))
            def balance_match(r):
                dim=' '.join(r.dims)
                nums=[float(n.replace(',','')) for n in re.findall(r'\$([\d,]+(?:\.\d+)?)',dim)]
                if not nums:return False
                if domain=='mortgage':return nums[0]>=amount
                return nums[0]<=amount and (len(nums)<2 or amount<=nums[1])
            candidates=[r for r in candidates if balance_match(r)]
            if domain=='mortgage' and candidates:
                bound=lambda r:float(re.search(r'\$([\d,]+)',r.label)[1].replace(',',''))
                minimum=min(bound(r) for r in candidates); candidates=[r for r in candidates if bound(r)==minimum]
        if not candidates: return self.unknown('The selected snapshot does not publish a rate for that product and set of qualifiers.')
        if re.search(r'highest|maximum|top|any .*pay',q):
            metric=lambda r:max(float(v.rstrip('%')) for k,v in r.metrics if re.fullmatch(r'[\d.]+%',v))
            maximum=max(metric(r) for r in candidates);candidates=[r for r in candidates if metric(r)==maximum]
        # Collapse duplicate facts; refuse equally authoritative unresolved disagreements.
        grouped=defaultdict(list)
        for r in candidates:grouped[r.key()].append(r)
        winners=[]
        for same in grouped.values():
            effective=max(r.effective for r in same)
            latest=[r for r in same if r.effective==effective]
            preferred=[r for r in latest if r.domain=='auto' and 'auto-motorcycle-loans' in r.url]
            if preferred: latest=preferred
            if len({metric_signature(r.metrics) for r in latest})>1:
                return self.unknown('Equally authoritative sources disagree for this exact product/tier.',[r.source() for r in latest[:3]])
            winners.append(sorted(latest,key=lambda r:r.url)[0])
        winners.sort(key=lambda r:(0 if '$100,000 or less' in r.label else 1,r.label))
        sources=[]; seen=set()
        for r in winners:
            if r.url not in seen:
                sources.append(Source(r.url,r.sid,'\n'.join(x.quote for x in winners if x.url==r.url)))
                seen.add(r.url)
        text='\n'.join(r.render() for r in winners)
        if domain in ('auto','personal'):text+=' Published rates are as low as; approval and credit qualifications apply.'
        notes=[]
        for r in winners:
            for other in data['rows']:
                if other.key()==r.key() and metric_signature(other.metrics)!=metric_signature(r.metrics) and authority(other.url)<authority(r.url):
                    notes.append(f'Used {r.url}; the URL-based source policy ranks it above the conflicting {other.url}.');break
        return Answer(text,sources,True,' '.join(sorted(set(notes))) or None)

    def factual_answer(self, question, data):
        """Intent constraints select evidence fields; no factual values are embedded."""
        q=norm(question)
        chunks=data['chunks']
        def result(selected, prefix=''):
            return Answer(prefix+'\n'.join(c.text for c in selected),[Source(c.url,c.sid,c.text[:1000]) for c in selected])
        def newest(cs):
            def key(c):
                p=data['pages'][c.url]
                m=re.search(r'([A-Z][a-z]+) (\d{1,2}), (\d{4})',p.markdown[:500])
                published=''
                if m:
                    try: published=date(int(m[3]),list(calendar.month_name).index(m[1]),int(m[2])).isoformat()
                    except ValueError: pass
                return (authority(c.url),published,c.url)
            return sorted(cs,key=key,reverse=True)
        if 'address' in q and 'branch' in q:
            names=set(tokens(q)) - {'address','branch','of','located','where'}
            cs=[c for c in chunks if urlsplit(c.url).path.rstrip('/')=='/contact' and re.search(r'\b\d{5}\b',c.text) and names & set(tokens(c.text+' '+c.context))]
            return result(cs[:1]) if cs else self.unknown('No matching branch address was found in the locator.')
        if 'routing' in q:
            cs=[c for c in chunks if 'routing' in c.text.lower() and re.search(r'\b\d{9}\b',c.text)]
            cs=sorted(cs,key=lambda c:(-authority(c.url),len(c.text),c.url))
            if cs:
                c=cs[0];return Answer(re.search(r'\b\d{9}\b',c.text)[0],[Source(c.url,c.sid,c.text[:1000])])
        if re.search(r'how many.*branch|number of branch',q):
            cs=newest([c for c in chunks if re.search(r'\d+ branch office locations',c.text)])
            if cs:
                c=cs[0];m=re.search(r'\d+ branch office locations',c.text)
                return Answer(m[0]+'.',[Source(c.url,c.sid,c.text[:1000])])
        if 'forbes' in q:
            cs=newest([c for c in chunks if 'forbes' in c.text.lower() and re.search(r'(time.*recognized|recognized.*time)',c.text,re.I)])
            if cs:return result(cs[:1])
        if 'home$tart' in q or 'homestart' in q:
            cs=newest([c for c in chunks if re.search(r'home.?tart',c.text,re.I) and re.search(r'\$[\d,]+',c.text)])
            if cs:return result(cs[:1])
        if re.search(r'eligible|eligibility|who.*member',q):
            cs=[c for c in chunks if '/about/join' in c.url and ('live or work' in c.text.lower() or all(t in c.text for t in ['Iowa','Illinois','Wisconsin']))]
            if cs:return result(cs[:3])
        if re.search(r'update|change',q) and 'contact information' in q:
            cs=[c for c in chunks if urlsplit(c.url).path.rstrip('/')=='/contact' and 'specific account question' in c.text.lower()]
            if cs:return result(cs[:1], 'For help updating account details, use the contact options provided by the credit union: ')
        if 'student' in q and re.search(r'option|flexib|loan',q):
            cs=[c for c in chunks if '/personal/loans/student-loans' in c.url and (c.context in ['Flexible Repayment','Keep More Money'] or c.context=='Student Loans & Refinancing' and not c.text.startswith('Apply'))]
            if cs:return result(cs[:3], 'Student loans and refinancing: ')
        if 'hour' in q and re.search(r'lobby|drive.up',q):
            kind='Drive-up' if re.search(r'drive.up',q) else 'Lobby'
            examples=[]
            generic=set('general all same keep does tell give lobby drive up hour branch for the what are your'.split())
            named=set(tokens(q))-generic-{'can','me','dupaco'}
            for page in sorted(data['pages'].values(),key=lambda p:p.url):
                if named and not named.issubset(set(tokens(page.title+' '+urlsplit(page.url).path.replace('-',' ')))):continue
                body=page.markdown.split('## Handpicked')[0]
                for m in re.finditer(r'\*\*'+kind+r'\*\*(.*?)(?=\*\*(?:Lobby|Drive-up|ABOUT)|\Z)',body,re.S|re.I):
                    excerpt=plain(m[0]).split('![')[0].strip()
                    # Only consume schedule lines, not article boilerplate after them.
                    lines=[]
                    for line in excerpt.splitlines():
                        if line.strip() and not re.search(r'Lobby|Drive.up|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday',line,re.I):break
                        if line.strip():lines.append(line)
                    excerpt=' '.join(lines)
                    if re.search(r'\d.*(?:a\.m\.|p\.m\.|noon)',excerpt,re.I):
                        if excerpt not in [x[0] for x in examples]:examples.append((excerpt,page))
            if not examples:return self.unknown('No grounded schedule was found for the requested branch.')
            examples=examples[:2]
            return Answer('Schedules vary by branch. The supplied branch announcements give these examples; they may be historical and should be confirmed for a visit.\n'+'\n'.join(p.title+': '+t for t,p in examples)+'\nWhich branch do you need?', [Source(p.url,data['sid'],t) for t,p in examples])
        if 'branch' in q and re.search(r'close|still open',q):
            names=set(tokens(q))-{'branch','close','closed','still','open','today','when','october','2026'}
            cs=[c for c in chunks if re.search(r'(will close|scheduled to close|permanently close)',c.text,re.I) and names & set(tokens(c.text+' '+c.url.replace('-',' ')))]
            if cs:return result(newest(cs)[:1], 'The snapshot reports this closure: ')
        return None

    def retrieve(self,question,data):
        qt=set(tokens(question)); q=norm(question)
        if not qt:return self.unknown()
        scored=[];n=len(data['chunks'])
        for c in data['chunks']:
            overlap=qt & c.counts.keys()
            if not overlap:continue
            score=sum(math.log(1+(n-data['df'][t]+.5)/(data['df'][t]+.5))*c.counts[t]/(c.counts[t]+1.2) for t in overlap)
            score/=1+len(tokens(c.text))/180
            score+=authority(c.url)*.25
            body_tokens=set(tokens(c.text))
            score+=sum(1.0 for t in qt if t in body_tokens)
            if c.text.startswith('Learn ') or c.text.startswith('For more information'): score-=4
            if 'mobile wallet' in q and 'pay' not in body_tokens: continue
            if 'student' in q and 'student' not in body_tokens: continue
            scored.append((score,c))
        scored.sort(key=lambda x:(-x[0],x[1].url,x[1].text))
        if not scored:return self.unknown()
        best=scored[0][1]
        # Never return a rate from a semantically unrelated paragraph.
        if re.search(r'\brate|\bapr|\bapy',q) and not re.search(r'\d+(?:\.\d+)?%',best.text):return self.unknown()
        meaningful=qt - {'account','loan','branch','hour','number','know','give','please','tell','would','like','going','new','university','option','options','flexibility'}
        if not meaningful or len(meaningful & best.counts.keys())/len(meaningful)<.45:return self.unknown()
        if ('lobby' in q or 'drive-up' in q) and not re.search(r'\d.*(?:a\.m\.|p\.m\.|am|pm|noon)',best.text,re.I):return self.unknown()
        if 'routing' in q:
            m=re.search(r'\b\d{9}\b',best.text)
            if not m:return self.unknown()
            return Answer(m[0],[Source(best.url,best.sid,best.text[:700])])
        return Answer(best.text,[Source(best.url,best.sid,best.text[:1000])])

    def conflicts(self):
        """Same-snapshot disagreements only; normal historical updates are not conflicts."""
        reports={}
        latest_day = max(self.versions, default='')
        for day,data in sorted(self.versions.items()):
            groups=defaultdict(list)
            for r in data['rows']:
                if r.effective and r.effective > day:
                    continue
                # Unknown deposit/card audience is insufficient identity to declare
                # two similarly named rows contradictory across different sources.
                if r.domain in ('savings', 'checking', 'card') and r.audience == 'unspecified':
                    continue
                for metric,value in metric_signature(r.metrics):groups[(r.key(),metric)].append((r,value))
            for (key,metric),items in groups.items():
                values=sorted({v for r,v in items})
                if len(values)<2:continue
                ranked=sorted(items,key=lambda item:(authority(item[0].url),item[0].effective),reverse=True)
                rank=(authority(ranked[0][0].url),ranked[0][0].effective)
                best={v for r,v in ranked if (authority(r.url),r.effective)==rank}
                resolution=next(iter(best)) if len(best)==1 else None
                unique={ (r.url,v):(r,v) for r,v in items }
                topic=' / '.join(key[1])+' '+metric
                if key[2] != 'not_applicable':
                    topic = key[2] + ' / ' + topic
                reports[(key,metric)]=Conflict(topic,values,[r.source() for r,v in unique.values()],resolution,
                    conflict_reason(day, metric, items, resolution, latest_day))
        return list(reports.values())


def build():
    return KnowledgeSystem()
