# Name: Jing Liu
# ID: 1140768
# Date: 2021-2-10






from flask import Flask, url_for, redirect, request, render_template, flash
import psycopg2
import connect
import re
import uuid

cur = None
app = Flask(__name__)


def getCursor():
    global cur
    if cur == None:
        con = psycopg2.connect(dbname=connect.dbname, user=connect.dbuser,
                               password=connect.dbpass, host=connect.dbhost, port=connect.dbport)
        con.autocommit = True
        cur = con.cursor()
        return cur
    else:
        return cur

def genID():
    return uuid.uuid4().fields[1]

def strip(obj):
    obj_s = str(obj)
    format = re.sub('[^A-Z^a-z^ ]', '', obj_s)
    return format

@app.route('/')
def home():
    return render_template('home.html')

# select all activitynights  suited for all youth
@app.route('/youth')
def youth():
    cur = getCursor()
    #the VIEW events is created in database which shows all activitynights for all club members
    events = cur.execute("SELECT distinct activitynightid, nighttitle, groupname, \
        activitynightdate FROM events WHERE dateofbirth > (current_date - interval \
            '18 year') order by groupname, activitynightdate;")
    events = cur.fetchall()
    colum_names = [desc[0] for desc in cur.description]
    return render_template('youth.html', events=events, colnames=colum_names)
    # display infomation and send user option to /youth/attend

# select all young members in one event 
@app.route('/youth/attend', methods=['POST', 'GET'])
def youth_attend():
    nightid = request.args.get('nightid')

    cur = getCursor()
    cur.execute("SELECT groupname as group,memberid,firstname,familyname,activitynightid,\
        nighttitle,activitynightdate as eventdate FROM events WHERE activitynightid = %s AND \
            dateofbirth > (current_date - interval '18 year') ORDER BY firstname", (nightid,))
    youth_events = cur.fetchall()

    colum_names = [desc[0] for desc in cur.description]

    return render_template('youth_attend_form.html', colnames=colum_names, nights=youth_events, nightid=nightid)
    # display selected info, with a form to collect input and send to /attend_confirm

# collect data from two forms (youth_attend_form, adult_attend_form) and insert into database
@app.route('/attend_confirm', methods=['POST', 'GET'])
def attend_confirm():
    if request.method == 'POST':
        results = request.form
        status = strip(results.get('status'))
        note = strip(results.get('note'))
        div = results.get('distinguish')
        #variable div is used to distinguish which form the data came from
        event_info = results.get('event')
        ids = event_info.split(',')
        memberid = int(ids[0])
        nightid = int(ids[1])
        #variable event_info contains two pieces of information joined by ',' 
        #TODO learn transmiting multiple information in one value through method POST

        cur = getCursor()
        # UNIQUE of activitynightid with memberid has created in database
        sql = "INSERT INTO attendance VALUES (%s, %s, '%s','%s') ON CONFLICT \
            (activitynightid,memberid) DO UPDATE SET attendancestatus = \
            EXCLUDED.attendancestatus, notes = EXCLUDED.notes " % (nightid, memberid, status, note)
        cur.execute(sql)

        cur.execute("SELECT memberid FROM member WHERE dateofbirth > (current_date - interval \
            '18 year')")
        if div == 'adult_by_group':
            cur.execute(
                "SELECT groupid FROM activitynight WHERE activitynightid = %s", (nightid,))
            groupid = cur.fetchone()
            return redirect(url_for("adult_attend_info", memberid=memberid, groupid=groupid))
            # return to the attendance info grouped by membername
        elif div == 'adult_by_event':
            cur.execute(
                "SELECT groupid FROM activitynight WHERE activitynightid = %s", (nightid,))
            groupid = cur.fetchone()
            return redirect(url_for("adult_attend_info", nightid = nightid, groupid=groupid))
            # return to the attendance info grouped by event
        else:
            cur.execute("SELECT distinct events.*, attendance.attendancestatus, attendance.notes from events \
                left join attendance on events.memberid = attendance.memberid AND events.activitynightid = \
                    attendance.activitynightid WHERE events.memberid = %s and attendance.activitynightid \
                    = %s", (memberid, nightid))
            info = cur.fetchall()
            colum_names = [desc[0] for desc in cur.description]
            return render_template('youth_confirm.html', infos=info, colnames=colum_names)
            # for youth user, return to a new html page showing the attendance status

# select all current adult member names and groups for user selecting
@app.route('/adult', methods=['POST', 'GET'])
def adult():
    cur = getCursor()
    # the VIEW currentgroupmember has been created in database
    names = cur.execute("SELECT distinct memberid, firstname, familyname FROM \
        currentgroupmember WHERE dateofbirth < (current_date - interval '18 year') \
            order by firstname;")
    names = cur.fetchall()
    groups = cur.execute("SELECT distinct groupname, groupid FROM currentgroupmember;")
    groups = cur.fetchall()
    # TODO link membername and group in html
    
    return render_template('adult.html', names=names, groups=groups)
    # send user choice to /adult/group_info

# get info from mutiple forms and view function
# display two table of Group member and events list
# return to group_info.html that contains user function on html: 
# update member info, add a new member, update event attendance status, add a new event
@app.route('/adult/group_info', methods=['POST', 'GET'])
def group_info():
    if request.method == 'POST':
        results = request.form
        memberid = int(results.get('a_name'))
        groupid = results.get('a_group')
    else:
        memberid = request.args.get('memberid')
        groupid = request.args.get('groupid')

    memberid = memberid
    # the VIEW allmember has been created in database
    sql = "SELECT distinct * FROM allmember WHERE groupid = '%s' order by leftdate \
        DESC, adultleader DESC, firstname;" % groupid
    cur = getCursor()
    groupmember = cur.execute(sql)
    groupmember = cur.fetchall()
    group_colum_names = [desc[0] for desc in cur.description]

    groupname = cur.execute(
        "SELECT groupname FROM activitygroup WHERE groupid = %s", (groupid,))
    groupname = strip(cur.fetchone()).capitalize()

    activitynights = cur.execute(
        "SELECT activitynightid, nighttitle, description, activitynightdate \
            FROM activitynight WHERE groupid = %s;", (groupid,))
    activitynights = cur.fetchall()
    night_colum_names = [desc[0] for desc in cur.description]

    return render_template('group_info.html', groupmembers=groupmember, 
            colnames=group_colum_names, groupname=groupname, events=activitynights, 
            event_cols=night_colum_names, groupid=groupid)
    

# get info from two hyperlinks on group_info.html
# return to adult_attend_form.html showing attendance status and events for user selecting
# then send info to /attend_confirm
@app.route('/adult/attend_info', methods=['POST', 'GET'])
def adult_attend_info():
    memberid = request.args.get('memberid')
    groupid = request.args.get('groupid')
    nightid = request.args.get('nightid')
    # use nightid to distingush where the request come from
    # if nightid, attendance info grouped by event
    if nightid:
        cur = getCursor()
        sql = "SELECT distinct events.*, attendance.attendancestatus, attendance.notes \
                FROM events  left join attendance on events.memberid = attendance.memberid\
                AND events.activitynightid = attendance.activitynightid WHERE events.activitynightid \
                = %s order by events.firstname;" %(nightid)
        cur.execute(sql)
        night_member = cur.fetchall()
        colum_names = [desc[0] for desc in cur.description]
        sql = "SELECT DISTINCT nighttitle, activitynightdate, groupname FROM events WHERE activitynightid = %s;" % nightid
        cur.execute(sql)
        nightinfo = cur.fetchone()
        nighttitle = nightinfo[0]
        nightdate = nightinfo[1]
        groupname = nightinfo[2]
        nightdate = str(nightdate).split('+')
        nightdate = nightdate[0]
        # this part needs to be simplified, timestamp is tricky 

        return render_template('adult_attend_form.html', nights = night_member, colnames=colum_names,
             nighttitle = nighttitle, nightdate = nightdate, groupname = groupname, groupid =groupid )

    # attendance grouped by member name
    else:
        cur = getCursor()
        cur.execute("SELECT distinct events.*, attendance.attendancestatus, attendance.notes \
                    FROM events  left join attendance on events.memberid = attendance.memberid\
                        AND events.activitynightid = attendance.activitynightid WHERE events.memberid \
                        = %s and events.groupid =  %s order by events.activitynightdate;", (memberid, groupid,))
        nights = cur.fetchall()
        colum_names = [desc[0] for desc in cur.description]
        membername = cur.execute(
            "SELECT firstname, familyname FROM events WHERE memberid = %s", (memberid,))
        membername = strip(cur.fetchone())
        groupname = cur.execute(
            "SELECT groupname FROM events WHERE groupid = %s", (groupid,))
        groupname = strip(cur.fetchone())
        

        return render_template('adult_attend_form.html', nights=nights, colnames=colum_names,
            membername=membername, groupname=groupname, groupid = groupid )

# collect info to update member details or add a new member
# redirect to /adult/attend_info after updating in database
@app.route('/adult/memberUpdate', methods=['GET', 'POST'])
def memberUpdate():
    if request.method == 'POST':
        memberid = int(request.form.get('memberid'))
        groupid = request.form.get('groupid')
        joineddate = request.form.get('joineddate')
        dates = joineddate.split(' ')
        joineddate = dates[0]
        leftdate = request.form.get('leftdate')
        leftd = leftdate.strip().lower() 
        if leftd == 'none' or '' or None: 
            leftdate = 'NULL'
        else:
            leftdate = f"'{leftd}'"
        # TODO to modify this part about datestamp format
        firstname = request.form.get('firstname')
        familyname = request.form.get('familyname')
        birthday = request.form.get('birthday')
        leader = request.form.get('leader')

        # unique of groupid with memberid in table groupmember has been created in database
        cur = getCursor()
        sql = "INSERT INTO groupmember VALUES (%s, %s, '%s',%s) ON CONFLICT \
            (groupid,memberid) DO UPDATE SET joineddate = \
            EXCLUDED.joineddate, leftdate = EXCLUDED.leftdate" % (memberid, groupid, joineddate, leftdate)
        cur.execute(sql)
        # unique of memberid in table member has been created in database
        sql = "INSERT INTO member VALUES (%s, '%s', '%s','%s', %s) ON CONFLICT \
            (memberid) DO UPDATE SET familyname = EXCLUDED.familyname, firstname \
            = EXCLUDED.firstname, dateofbirth = EXCLUDED.dateofbirth, adultleader \
            = EXCLUDED.adultleader" % (memberid, familyname, firstname, birthday, leader)
        cur.execute(sql)
        return redirect(url_for("group_info", memberid=memberid, groupid=groupid))
    else:
        memberid = request.args.get('memberid')
        groupid = request.args.get('groupid')
        if memberid:
            cur = getCursor()
            sql = "SELECT * FROM allmember WHERE memberid = %s AND groupid= %s;" % (memberid, groupid)
            cur.execute(sql)
            select_result = cur.fetchone()
            return render_template('memberform.html', memberdetails=select_result)
        else:
            id = genID()
            return render_template('memberform.html', groupid=groupid, memberid=id, memberdetails=False)

# collect info to add a new event 
# redirect to /adult/attend_info after updating in database
@app.route('/adult/activitynight', methods=['GET', 'POST'])
def activitynight():
    cur = getCursor()
    if request.method == 'POST':
        results = request.form
        nightid = genID()
        groupid = int(results.get('groupid'))
        nighttitle = results.get('nighttitle')
        nightdate = results.get('nightdate')
        description = results.get('description')

        sql = "INSERT INTO activitynight VALUES (%s, '%s', '%s', '%s', '%s')" % (
            nightid, groupid, nighttitle, description, nightdate)
        cur.execute(sql)
        return redirect(url_for("group_info",  groupid=groupid))

    else:
        groupname = request.args.get('groupname')
        groupname = groupname.lower()
        groupid = cur.execute("SELECT groupid FROM activitygroup WHERE groupname = %s", (groupname,))
        groupid = cur.fetchone()
        return render_template('actnight_form.html', groupid=groupid, groupname=groupname)

if __name__ == '__main__':
    app.run(debug=True)
