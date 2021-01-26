import getpass, imaplib, email.parser

IMAP = imaplib.IMAP4_SSL('outlook.office365.com', 993)
IMAP.login( 'username', getpass.getpass() )
typ, messages = IMAP.select( '"Large emails"', True)
if messages != 0 :
    typ, msg = IMAP.fetch( "1", '(BODY[])')
newMsg = email.message_from_bytes( msg[0][1] )
print( newMsg.is_multipart() )
for part in newMsg.walk() :
    print( part.get_content_type() )