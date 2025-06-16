from app import app, db, User  # Adjust this name if needed

# Create users inside Flask app context
with app.app_context():
    # Master user
    master = User(username='masteruser', role='master')
    master.set_password('masterpass')

    # Limited users for specific YTM units
    ytm1 = User(username='ytm1user', role='limited', unit='YTM-1')
    ytm1.set_password('ytm1pass')

    ytm2 = User(username='ytm2user', role='limited', unit='YTM-2')
    ytm2.set_password('ytm2pass')

    ytm3 = User(username='ytm3user', role='limited', unit='YTM-3')
    ytm3.set_password('ytm3pass')

    ytm7 = User(username='ytm7user', role='limited', unit='YTM-7')
    ytm7.set_password('ytm7pass')

    # Add all users to the session
    db.session.add_all([master, ytm1, ytm2, ytm3, ytm7])
    db.session.commit()

    print("✅ Users added successfully!")
