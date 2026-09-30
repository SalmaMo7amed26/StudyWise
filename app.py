import streamlit as st
import sqlite3
import base64
from pathlib import Path
from datetime import date, datetime, timedelta

DB="studywise.db"
SUBJECTS=["Machine Learning","Cloud Computing","Data Science Practice","Computer Networks","Operations Research","Technical Report Writing"]
DAYS=["Saturday","Sunday","Monday","Tuesday","Wednesday","Thursday","Friday"]
AR={d:d for d in DAYS}

# Status per lecture/lab: 0 not taken yet, 1 taken but not studied, 2 studying now, 3 done
STATUS_LABELS=["⚪ Not attended yet","🟠 Attended, not studied","🟡 Studying now","🟢 Done studying"]
STATUS_WEIGHT=[0,0.15,0.6,1.0]

# Group B timetable from the timetable screenshots.
SCHEDULE={
"Saturday":[("Machine Learning","Lecture","11:00 - 12:30","B","A210"),("Data Science Practice","Lecture","14:15 - 15:45","B","B201")],
"Sunday":[("Cloud Computing","Lab","09:30 - 11:00","B-1","M2.202"),("Cloud Computing","Lecture","11:00 - 12:30","B","A210"),("Computer Networks","Lab","12:45 - 14:15","B-1","A412"),("Data Science Practice","Lab","14:15 - 15:45","B-1","A405")],
"Monday":[],"Tuesday":[],
"Wednesday":[("Machine Learning","Lab","12:45 - 14:15","B-1","M2.402"),("Operations Research","Lecture","14:15 - 15:45","B","A210")],
"Thursday":[("Computer Networks","Lecture","11:00 - 12:30","B","A201"),("Operations Research","Lab","12:45 - 14:15","B-1","A319"),("Technical Report Writing","Lecture","14:15 - 15:45","B","A201")],
"Friday":[]
}

st.set_page_config(page_title="StudyWise",page_icon="📚",layout="wide")
background_path=Path(__file__).with_name("background.jpeg")
background_data=base64.b64encode(background_path.read_bytes()).decode("ascii") if background_path.exists() else ""
st.markdown(f"""<style>
.stApp{{background:linear-gradient(rgba(255,255,255,.58),rgba(255,255,255,.58)),url("data:image/jpeg;base64,{background_data}") center/cover fixed no-repeat}}
.block-container{{padding-top:1.2rem;padding-bottom:2rem}}
.hero{{padding:24px;border-radius:22px;background:linear-gradient(120deg,rgba(255,255,255,.91),rgba(245,240,255,.88));border:1px solid rgba(255,255,255,.9);box-shadow:0 10px 30px rgba(71,76,130,.09)}}
[data-testid="stVerticalBlockBorderWrapper"]{{background:rgba(255,255,255,.62);border-color:rgba(157,169,210,.32)!important;border-radius:16px}}
[data-testid="stSidebar"]{{background:rgba(255,255,255,.72)}}
h1,h2,h3{{color:#34436b}}
</style>""",unsafe_allow_html=True)

def db():
    return sqlite3.connect(DB,check_same_thread=False)
def run(sql,args=(),fetch=False):
    c=db();cur=c.cursor();cur.execute(sql,args)
    out=cur.fetchall() if fetch else None
    c.commit();c.close();return out
def init():
    run("""CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY,subject TEXT,item_type TEXT,title TEXT,studied INTEGER DEFAULT 0,notes TEXT DEFAULT '')""")
    try:
        run("ALTER TABLE lessons ADD COLUMN status INTEGER DEFAULT 0")
        # first time this column is added: old "studied" items become done
        run("UPDATE lessons SET status=3 WHERE studied=1")
    except sqlite3.OperationalError:
        pass  # column already exists
    run("""CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,subject TEXT,title TEXT,item_type TEXT,due_date TEXT,status INTEGER DEFAULT 0,notes TEXT DEFAULT '')""")
    run("""CREATE TABLE IF NOT EXISTS grades(id INTEGER PRIMARY KEY,subject TEXT,category TEXT,title TEXT,score REAL,max_score REAL,grade_date TEXT)""")
    run("""CREATE TABLE IF NOT EXISTS study_notes(id INTEGER PRIMARY KEY,text TEXT,added_date TEXT,done INTEGER DEFAULT 0)""")
    run("""CREATE TABLE IF NOT EXISTS weekly_plan(id INTEGER PRIMARY KEY,day TEXT,item_order INTEGER,label TEXT,tier INTEGER)""")
    for alter in ["ALTER TABLE study_notes ADD COLUMN day TEXT DEFAULT ''","ALTER TABLE weekly_plan ADD COLUMN pdate TEXT DEFAULT ''"]:
        try: run(alter)
        except sqlite3.OperationalError: pass
    if run("SELECT COUNT(*) FROM lessons",fetch=True)[0][0]==0:
        for s in SUBJECTS:
            for k in ["Lecture","Lab"]:
                for i in range(1,8):
                    run("INSERT INTO lessons(subject,item_type,title) VALUES(?,?,?)",(s,k,f"{k} {i}"))
init()

def grade_sum(s):
    x=run("SELECT score,max_score FROM grades WHERE subject=?",(s,),True)
    return sum(a for a,b in x),sum(b for a,b in x)

# Study slots available per day (busy class days get fewer)
CAPACITY={"Saturday":2,"Sunday":2,"Monday":4,"Tuesday":4,"Wednesday":3,"Thursday":2,"Friday":2}

def generate_weekly_plan():
    """Builds a 7-day plan from today: deadlines + unfinished study + extra notes + daily class load."""
    today=date.today()
    dates=[today+timedelta(days=i) for i in range(7)]
    names=[d.strftime("%A") for d in dates]
    cap={d:CAPACITY[d.strftime("%A")] for d in dates}
    load={d:0 for d in dates}
    plan={d:[] for d in dates}

    def place(label,tier,allowed):
        allowed=allowed or dates
        best=min(allowed,key=lambda d:(load[d]/cap[d],dates.index(d)))
        plan[best].append((label,tier)); load[best]+=1

    # 1) tasks with deadlines: placed before the due date
    pending=run("SELECT subject,title,item_type,due_date FROM items WHERE status=0 ORDER BY due_date",fetch=True)
    for sub,title,typ,d in pending:
        due=None
        if d:
            try: due=datetime.strptime(d,"%Y-%m-%d").date()
            except: pass
        if due is None:
            place(f"🎯 {sub} — {title} ({typ})",0,None); continue
        due_txt=due.strftime("%d/%m")
        if due<today:
            place(f"🎯 {sub} — {title} ({typ}) ⚠️ overdue since {due_txt}",0,dates[:2])
        else:
            allowed=[x for x in dates if x<=due]
            # prefer finishing a day before the due date
            before=[x for x in allowed if x<due] or allowed
            place(f"🎯 {sub} — {title} ({typ}) · due {due_txt}",0,before)

    # 2) extra notes (may have a fixed day)
    for text,dname in run("SELECT text,day FROM study_notes WHERE done=0 ORDER BY id",fetch=True):
        allowed=[d for d in dates if dname and d.strftime("%A")==dname]
        place(f"📌 {text}",1,allowed)

    # 3) taken lectures/labs not fully studied (not studied at all first)
    for sub,typ,title,st_ in run("SELECT subject,item_type,title,status FROM lessons WHERE status IN (1,2) ORDER BY status,subject,item_type,id",fetch=True):
        tag="attended, not studied" if st_==1 else "studying now"
        place(f"📖 {sub} — {title} ({typ}) - {tag}",2 if st_==1 else 3,None)

    run("DELETE FROM weekly_plan")
    for d in dates:
        for order,(label,tier) in enumerate(sorted(plan[d],key=lambda t:t[1])):
            run("INSERT INTO weekly_plan(day,item_order,label,tier,pdate) VALUES(?,?,?,?,?)",(d.strftime("%A"),order,label,tier,d.isoformat()))
    return plan

page=st.sidebar.radio("📚 StudyWise",["🏠 Dashboard","📚 Subjects","📝 Tasks","📅 Schedule","🧠 Study Plan","🎯 Grades"])

if page=="🏠 Dashboard":
    st.markdown('<div class="hero"><h1>Welcome, SoSo 👋</h1><p style="font-size:1.6rem;line-height:2;margin:6px 0 0;direction:rtl;text-align:center">«رَبِّ اشْرَحْ لِي صَدْرِي وَيَسِّرْ لِي أَمْرِي»</p></div>',unsafe_allow_html=True)
    today=date.today()
    tasks=run("SELECT id,subject,title,item_type,due_date,status FROM items ORDER BY due_date",fetch=True)
    pending=[x for x in tasks if not x[5]]
    close=[]
    for x in pending:
        if x[4]:
            try:
                d=datetime.strptime(x[4],"%Y-%m-%d").date()
                if d>=today: close.append((d,x))
            except: pass
    close.sort()
    a,b,c=st.columns(3)
    a.metric("Open tasks",len(pending))
    b.metric("Due in 7 days",sum(d<=today+timedelta(days=7) for d,x in close))
    ts=sum(grade_sum(s)[0] for s in SUBJECTS); tm=sum(grade_sum(s)[1] for s in SUBJECTS)
    c.metric("Grades recorded",f"{ts:g}/{tm:g}" if tm else "0")

    behind=run("SELECT subject,item_type,title FROM lessons WHERE status=1 ORDER BY subject,item_type,id",fetch=True)
    if behind:
        st.subheader(f"🟠 {len(behind)} item(s) attended but not studied yet")
        for s,k,title in behind:
            st.write(f"- {s} — {title} ({k})")

    st.subheader("⏰ Coming up next")
    for d,x in close[:5]:
        with st.container(border=True):
            col1,col2=st.columns([.8,.2])
            col1.write(f"**{x[2]}** — {x[1]} · {x[3]} · {d.strftime('%d/%m/%Y')}")
            if col2.button("Done",key=f"d{x[0]}"):
                run("UPDATE items SET status=1 WHERE id=?",(x[0],));st.rerun()
    st.subheader("📊 Subject progress")
    for s in SUBJECTS:
        rows=run("SELECT status FROM lessons WHERE subject=?",(s,),True)
        total=len(rows)
        pct=sum(STATUS_WEIGHT[r[0]] for r in rows)/total if total else 0
        sc,mx=grade_sum(s)
        st.write(f"**{s}** — Study {pct:.0%} | Coursework: {sc:g}/{mx:g}" if mx else f"**{s}** — Study {pct:.0%} | Coursework: —")
        st.progress(pct)

elif page=="📚 Subjects":
    st.title("📚 Subjects")
    s=st.selectbox("Subject",SUBJECTS)
    sc,mx=grade_sum(s)
    rows_s=run("SELECT status FROM lessons WHERE subject=?",(s,),True)
    total=len(rows_s)
    done=sum(1 for r in rows_s if r[0]==3)
    pct=sum(STATUS_WEIGHT[r[0]] for r in rows_s)/total if total else 0
    x,y,z=st.columns(3);x.metric("Done studying",f"{done}/{total}");y.metric("Progress",f"{pct:.0%}" if total else "0%");z.metric("Coursework",f"{sc:g}/{mx:g}" if mx else "—")
    st.subheader("🎓 Lectures / Labs")
    for lid,k,title,status,notes in run("SELECT id,item_type,title,status,notes FROM lessons WHERE subject=? ORDER BY item_type,id",(s,),True):
        a,b,c=st.columns([.3,.28,.42])
        a.write(f"**{title}** · {k}")
        nv=b.selectbox("Status",STATUS_LABELS,index=status,key=f"l{lid}",label_visibility="collapsed")
        nn=c.text_input("Note",notes or "",key=f"n{lid}",label_visibility="collapsed")
        nv_idx=STATUS_LABELS.index(nv)
        if nv_idx!=status or nn!=(notes or ""):
            run("UPDATE lessons SET status=?,studied=?,notes=? WHERE id=?",(nv_idx,int(nv_idx==3),nn,lid));st.rerun()
    with st.form("newlesson"):
        k=st.selectbox("New type",["Lecture","Lab"]); title=st.text_input("Name")
        if st.form_submit_button("Add") and title.strip():
            run("INSERT INTO lessons(subject,item_type,title) VALUES(?,?,?)",(s,k,title.strip()));st.rerun()

elif page=="📝 Tasks":
    st.title("📝 Assignments / Quizzes / Projects")
    with st.form("task"):
        a,b=st.columns(2);s=a.selectbox("Subject",SUBJECTS);typ=b.selectbox("Type",["Assignment","Quiz","Project","Midterm","Other"])
        title=st.text_input("Task name"); d=st.date_input("Due date",date.today()); note=st.text_input("Notes")
        if st.form_submit_button("➕ Add") and title.strip():
            run("INSERT INTO items(subject,title,item_type,due_date,notes) VALUES(?,?,?,?,?)",(s,title.strip(),typ,d.isoformat(),note));st.rerun()
    rows=run("SELECT id,subject,title,item_type,due_date,status,notes FROM items ORDER BY due_date",fetch=True)
    for rid,s,title,typ,d,status,note in rows:
        with st.container(border=True):
            ca,cb=st.columns([.92,.08])
            done=ca.checkbox(f"**{title}** — {s} · {typ} · 📅 {d}",bool(status),key=f"t{rid}")
            if done!=bool(status):
                run("UPDATE items SET status=? WHERE id=?",(int(done),rid));st.rerun()
            if cb.button("🗑️",key=f"td{rid}",help="Delete task"):
                run("DELETE FROM items WHERE id=?",(rid,));st.rerun()
            if note: st.caption(note)

elif page=="📅 Schedule":
    st.title("📅 Weekly Schedule")
    for day in DAYS:
        with st.container(border=True):
            st.subheader(day)
            if not SCHEDULE[day]:
                st.success("🌿 Friday: rest and optional light review." if day=="Friday" else "🧠 Main study / make-up day.")
            else:
                for s,k,t,g,r in SCHEDULE[day]:
                    st.write(f"**{t}** — {s} · {k} · {g} · {r}")

elif page=="🧠 Study Plan":
    st.title("🧠 Weekly Study Plan")

    with st.form("extra_note",clear_on_submit=True):
        st.write("Something else on your plate that isn't tracked here? (late study, revision, personal stuff...)")
        c1,c2=st.columns([.7,.3])
        txt=c1.text_input("Write it here")
        dchoice=c2.selectbox("Day",["Any suitable day"]+[AR[d] for d in DAYS])
        if st.form_submit_button("➕ Add") and txt.strip():
            dname=next((k for k,v in AR.items() if v==dchoice),"")
            run("INSERT INTO study_notes(text,added_date,day) VALUES(?,?,?)",(txt.strip(),date.today().isoformat(),dname));st.rerun()

    notes=run("SELECT id,text,done,day FROM study_notes ORDER BY id DESC",fetch=True)
    if notes:
        st.write("**Extra items:**")
        for nid,text,done,dname in notes:
            a,b=st.columns([.9,.1])
            nv=a.checkbox(text+(f"  ·  {AR[dname]}" if dname in AR else ""),bool(done),key=f"sn{nid}")
            if nv!=bool(done):
                run("UPDATE study_notes SET done=? WHERE id=?",(int(nv),nid));st.rerun()
            if b.button("🗑️",key=f"snd{nid}"):
                run("DELETE FROM study_notes WHERE id=?",(nid,));st.rerun()

    st.divider()
    if st.button("🧠 Create table",type="primary"):
        generate_weekly_plan();st.rerun()

    rows=run("SELECT day,label,tier,pdate FROM weekly_plan ORDER BY pdate,item_order",fetch=True)
    if not rows:
        st.info("No plan yet. Press Create table.")
    else:
        order=[];plan={}
        for day,label,tier,pdate in rows:
            key=(pdate,day)
            if key not in plan: plan[key]=[];order.append(key)
            plan[key].append(label)
        for pdate,day in order:
            with st.container(border=True):
                try: dtxt=datetime.strptime(pdate,"%Y-%m-%d").strftime("%d/%m")
                except: dtxt=""
                st.subheader(f"{day} — {dtxt}")
                cls=SCHEDULE.get(day,[])
                if cls:
                    st.caption("📚 Classes today: "+" · ".join(f"{k} {s} ({t.split(' - ')[0]})" for s,k,t,g,r in cls))
                for label in plan[(pdate,day)]:
                    st.write(f"- {label}")
                if not plan[(pdate,day)]:
                    st.success("No study load 🌿")
        st.caption("🎯 Deadline · 📌 Extra item · 📖 Attended lecture/lab not fully studied")

elif page=="🎯 Grades":
    st.title("🎯 Coursework Grades")
    with st.form("grade"):
        a,b=st.columns(2);s=a.selectbox("Subject",SUBJECTS);cat=b.selectbox("Category",["Quiz","Midterm","Assignment","Project","Other"])
        c,d=st.columns(2);score=c.number_input("Your score",0.0,1000.0,0.0,.5);mx=d.number_input("Out of",0.5,1000.0,10.0,.5)
        if st.form_submit_button("➕ Save"):
            run("INSERT INTO grades(subject,category,title,score,max_score,grade_date) VALUES(?,?,?,?,?,?)",(s,cat,"",score,mx,date.today().isoformat()));st.rerun()
    for s in SUBJECTS:
        sc,mx=grade_sum(s)
        with st.expander(f"{s} — {sc:g}/{mx:g}" if mx else s):
            for gid,cat,title,score,mx2,d in run("SELECT id,category,title,score,max_score,grade_date FROM grades WHERE subject=? ORDER BY id DESC",(s,),True):
                ga,gb=st.columns([.92,.08])
                ga.write(f"**{cat}**{' · '+title if title else ''} · {score:g}/{mx2:g} · {d}")
                if gb.button("🗑️",key=f"gd{gid}",help="Delete grade"):
                    run("DELETE FROM grades WHERE id=?",(gid,));st.rerun()
            if mx: st.progress(min(sc/mx,1))
