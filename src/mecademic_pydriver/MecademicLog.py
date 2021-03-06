
from collections import deque

from mecademic_pydriver.MessageReceiver import MessageReceiver
from mecademic_pydriver.parsingLib import messages2codepayload

class MecademicLog:
    """
    Class that represents the log of all messages received from mecademic robot

    Attributes:
        log: a deque of last logs received each one is a tuple (code, payload)
        log_size: maximum log size
    """
    
    def __init__(self, socket, log_size=100, on_new_messages_received=None):
        """
        Constructor
        socket: the socket object
        log_size: (int) the max log size
        on_new_messages_received(): callbk that takes a list of tuple as input, it is called when received new messages
                                    each tuple is (code, payload) 
                                    usefull to intercept new messages without remove them from the log
        """
        self.message_receiver = MessageReceiver(socket, "\x00")
        self.log = deque([],log_size)
        self.on_new_messages_received_cb = on_new_messages_received


    def get_log(self):
        """
        Get a copy of the log as a list object
        """
        return list(self.log)

    def update_log(self, wait_for_new_messages=False, timeout=None):
        """
        Update the log reading messages from the socket
        wait_for_new_messages : bool (Defult False)
            If True, wait for new messages
        timeout : same meaning of select.select, used only when wait_for_new_messages=True
        """
        if wait_for_new_messages:
            self.message_receiver.wait_for_new_messages(timeout)

        messages = messages2codepayload( 
                    self.message_receiver.get_last_messages(
                        self.log.maxlen
                        )
                    )
        
        if messages:
            #call the callbk on new messages
            if self.on_new_messages_received_cb:
                self.on_new_messages_received_cb(messages)

            self.log.extend(messages)

    def get_first_message(self):
        """
        Get the first message in the log
        Remove the message from the log
        Return None if no message is in the log
        """
        if self.log:
            return self.log.popleft()
        else:
            return None

    def get_last_message(self):
        """
        Get the last message in the log
        Remove the message from the log
        Return None if no message is in the log
        """
        if self.log:
            return self.log.pop()
        else:
            return None

    def get_last_code_occurance(self, code, delete_others = False):
        """
        Get message corresponding to the last occurence of the corresponding code
        Remove the message from the log
        Return None if no message found
        code : str
            The code to search - the code is found if the error code starts with the provided one
        delete_others : bool (Default False)
            Delete all other occurances of the same code
        """
        message = None
        # find message
        for this_message in reversed(self.log):
            if this_message[0].startswith(code):
                message = this_message
                break
        #if found remove it from log
        if message:
            if delete_others:
                self.remove_all_code(code)
            else:
                self.log.reverse()
                self.log.remove(message)
                self.log.reverse
        return message
    
    def remove_all_code(self, code):
        """
        Remove all occurences of code in the log
        """
        messages_to_remove = []
        for message in self.log:
            if message[0].startswith(code):
                messages_to_remove.append(message)
        for message in messages_to_remove:
            self.log.remove(message)

    def get_all_messages(self,code):
        """
        Get all messages from the Log
        Clear the log
        return [] if the log is empty
        """
        messages = list(self.log)
        self.clear_log()
        return messages

    def clear_log(self):
        """
        Clear all messages from the log
        """
        self.log.clear()