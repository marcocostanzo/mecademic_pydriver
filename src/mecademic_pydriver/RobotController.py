import socket
import time

from mecademic_pydriver.MecademicLog import MecademicLog
from mecademic_pydriver.parsingLib import payload2tuple, build_command

class RobotController:
    """Class for the Mecademic Robot allowing for communication and control of the 
    Mecademic Robot with all of its features available

    Attributes:
        Address: IP Address
        socket: socket connecting to physical Mecademic Robot
        End of Block: Setting for EOB reply
        End of Movement: Setting for EOM reply
        Error: Error Status of the Mecademic Robot
    """
    def __init__(
        self, 
        address, 
        socket_timeout=0.1,
        motion_commands_response_timeout=0.001,
        log_size=100, 
        on_new_messages_received=None
        ):
        """Constructor for an instance of the Class Mecademic Robot 

        :param address: The IP address associated to the Mecademic Robot
        """
        self.address = address
        self.port = 10000

        self.socket = None
        self.socket_timeout = socket_timeout

        self.motion_commands_response_timeout = motion_commands_response_timeout

        self.mecademic_log = None
        self.log_size = log_size
        self.on_new_messages_received = on_new_messages_received

    def connect(self):
        """
        Connects Mecademic Robot object communication to the physical Mecademic Robot

        May raise an Exception
        """

        if self.socket:
            return #already conencted

        #create a socket and connect
        self.socket = socket.socket()
        self.socket.settimeout(self.socket_timeout)
        self.socket.connect((self.address, self.port))
        self.socket.settimeout(self.socket_timeout)

        #check that socket is not connected to nothing
        if self.socket is None:          
            raise RuntimeError( "RobotFeedback::Connect - socket is None" )

        self.mecademic_log = MecademicLog(
                                self.socket, 
                                log_size=self.log_size, 
                                on_new_messages_received=self.on_new_messages_received
                                )

        self.mecademic_log.update_log(wait_for_new_messages=True)

        #check if error 3001
        self.handle_specific_error("3001", method_str="connect")
        self.handle_errors(method_str="connect")

        #check if message 3000
        self.check_response(["3000"], method_str="check_reconnectsponse")

    def disconnect(self):
        """
        Disconnects Mecademic Robot object from physical Mecademic Robot
        """
        if(self.socket is not None):
            self.socket.close()
            self.socket = None

    def check_response(self, codes, method_str="check_response"):
        """
        If the code is not present il the log: raise an exception
        codes: a list of codes to check
        method_str : the method that generated the error
        """
        if not codes:
            return
        for code in codes:
            msg = self.mecademic_log.get_last_code_occurance(
                                code, 
                                delete_others = True
                                )
            if msg:
                return
        raise RuntimeError("RobotController::{} code {} not found in log".format(method_str,codes))

    def handle_specific_error(self, code, method_str="handle_specific_error"):
        """
        If the code is present il the log: raise an exception
        method_str : the method that generated the error
        """
        error_msg = self.mecademic_log.get_last_code_occurance(
                            code, 
                            delete_others = True
                            )
        if error_msg:
            raise RuntimeError("RobotController::{} {}".format(method_str,error_msg))

    def handle_errors(self, method_str="handle_errors", delete_others = False):
        """
        Generic error handler
        Check if a error code is present in the log
        then raise an exception
        delete_others: bool (Default False)
            if True, delete all errors from the log
        """
        error_msg = self.mecademic_log.get_last_code_occurance(
                            "1", # error code starts with 1
                            delete_others = False
                            )
        if error_msg:
            raise RuntimeError("RobotController::{} {}".format(method_str,error_msg))

    def send_string_command(self, cmd):
        """
        Sends a string command to the physical Mecademic Robot

        :param cmd: Command to be sent  (string)

        May raise exceptions
        This function does not check if robot is in error
        """
        command = cmd + '\0'
        self.socket.sendall(command.encode("ascii"))

    def send_command_handled(
                            self,
                            cmd,
                            method_str="send_command_handled",
                            codes_to_remove_from_log=[],
                            errors_code=[],
                            responses_code=[],
                            handle_all_errors=True,
                            wait_for_new_messages=True, timeout=None
                            ):
        """
        Send a command and handle errors
        codes_to_remove_from_log: [str]
            remove this codes from the log before
        error_codes : [str]
            command specific error codes - if any of this code is returned, raises an error
        responses_codes : [str]
            responses of the command - raises an error if not found
        handle_all_errors: bool (Default True)
            If true - raises an error on any error (code starts with 1)
        wait_for_new_messages and  timeout: are passed to self.mecademic_log.update_log
            meaning: if wait for new messages and the waiting timeout in seconds (None=Forever 0=poll)
        """

        #Update Log in Polling mode, remove all message with code in [codes_to_remove_from_log]
        #This is useful to forget errors that will be cleared by this command
        self.mecademic_log.update_log(wait_for_new_messages=False)
        for code in codes_to_remove_from_log:
            self.mecademic_log.remove_all_code(code)

        #send the command
        self.send_string_command(cmd)

        #update the log
        self.mecademic_log.update_log(wait_for_new_messages=wait_for_new_messages, timeout=timeout)
        #check command specific errors
        for code in errors_code:
            self.handle_specific_error(code, method_str=method_str)
        #check generic errors
        if handle_all_errors:
            self.handle_errors(method_str=method_str)
        #check the response
        try:
            self.check_response(responses_code, method_str=method_str)
        except RuntimeError:
            #try to receive again
            print("[WARNING] RobotController::send_command_handled response not received, retry...")
            self.mecademic_log.update_log(wait_for_new_messages=wait_for_new_messages, timeout=timeout)
            self.handle_errors(method_str=method_str)
            self.check_response(responses_code, method_str=method_str)

    ################################################
    ###     REQUEST COMMANDS                    ####
    ################################################

    def ActivateRobot(self):
        """
        Call the ActivateRobot request command
        """
        self.send_command_handled(
            "ActivateRobot",
            method_str="ActivateRobot",
            codes_to_remove_from_log=["1005"],
            errors_code=["1013"],
            responses_code=["2000","2001"])

    def ClearMotion(self):
        """
        Call the ClearMotion request command
        """
        self.send_command_handled(
            "ClearMotion",
            method_str="ClearMotion",
            errors_code=[],
            responses_code=["2044"])

    def DeactivateRobot(self):
        """
        Call the DeactivateRobot request command
        """
        self.send_command_handled(
            "DeactivateRobot",
            method_str="DeactivateRobot",
            codes_to_remove_from_log=["1005"],
            errors_code=[],
            responses_code=["2004"])

    def GetConf(self, retry=True):
        """
        Call the GetConf request command
        retry : bool (Default True)
            If no response, Retry one time
        Return a dictionary {'c1':c1,'c3':c3,'c5':c5}
        """
        #not handle any error!
        #send command
        self.send_string_command("GetConf")
        #update the log
        self.mecademic_log.update_log(wait_for_new_messages=True)

        self.handle_errors(method_str="GetConf")

        msg = self.mecademic_log.get_last_code_occurance(
                                "2029", 
                                delete_others = True
                                )
        if (not msg) and retry:
            print("[WARNING] RobotController::GetConf response not received, retry...")
            return self.GetConf(retry=False)
        conf = payload2tuple(msg[1], output_type = int)
        return {
            "c1": conf[0],
            "c3": conf[1],
            "c5": conf[2]
        }

    def GetStatusRobot(self, retry=True):
        """
        Call the GetStatusRobot request command
        retry : bool (Default True)
            If no response, Retry one time
        Return a dictionary {'as':as,'hs':hs, ... , 'eom':eom}
        """
        #not handle any error!
        #send command
        self.send_string_command("GetStatusRobot")
        #update the log
        self.mecademic_log.update_log(wait_for_new_messages=True)

        msg = self.mecademic_log.get_last_code_occurance(
                                "2007", 
                                delete_others = True
                                )
        if (not msg) and retry:
            print("[WARNING] RobotController::GetStatusRobot response not received, retry...")
            return self.GetStatusRobot(retry=False)
        status = payload2tuple(msg[1], output_type = int)
        return {
            "as": status[0],
            "hs": status[1],
            "sm": status[2],
            "es": status[3],
            "pm": status[4],
            "eob": status[5],
            "eom": status[6]
        }

    def Home(self):
        """
        Call the Home request command
        """
        self.send_command_handled(
            "Home",
            method_str="Home",
            codes_to_remove_from_log=["1006"],
            errors_code=["1014"],
            responses_code=["2002","2003"])

    def ResetError(self):
        """
        Call the ResetError request command
        """
        #remove all errors from the log then call ResetError command
        self.send_command_handled(
            "ResetError",
            method_str="ResetError",
            codes_to_remove_from_log=["1"],
            errors_code=["1025"],
            handle_all_errors=False,
            responses_code=["2005","2006"])
        self.mecademic_log.update_log(wait_for_new_messages=False)
        self.mecademic_log.remove_all_code("1")

    def ResumeMotion(self):
        """
        Call the ResumeMotion request command
        """
        self.send_command_handled(
            "ResumeMotion",
            method_str="ResumeMotion",
            errors_code=[],
            responses_code=["2043"])

    def SetEOB(self,e):
        """
        Call the SetEOB request command
        """
        responses_code=[]
        if e == 0:
            responses_code = ["2055"]
        elif e == 1:
            responses_code = ["2054"]
        else:
            raise ValueError("RobotController::SetEOB invalid argument e={}".format(e))

        cmd = build_command("SetEOB",[e])
        self.send_command_handled(
            cmd,
            method_str="cmd",
            errors_code=[],
            responses_code=responses_code)

    def SetEOM(self,e):
        """
        Call the SetEOM request command
        """
        responses_code=[]
        if e == 0:
            responses_code = ["2053"]
        elif e == 1:
            responses_code = ["2052"]
        else:
            raise ValueError("RobotController::SetEOM invalid argument e={}".format(e))

        cmd = build_command("SetEOM",[e])
        self.send_command_handled(
            cmd,
            method_str="cmd",
            errors_code=[],
            responses_code=responses_code)

    ################################################
    ###     MOTION COMMANDS                    #####
    ################################################

    def update_log_for_motion_commands(self):
        """
        Update the log for the motion commands in a non bloking fashion
        """
        self.mecademic_log.update_log(wait_for_new_messages=True,timeout=self.motion_commands_response_timeout)

    def MoveJoints(self, joints):
        """
        Call the MoveJoints Motion Command
        joints: joints list [A1,A2,...,A6] in [deg]
        this methods does not check the response
        """
        if not len(joints)==6:
            raise ValueError("RobotController::MoveJoints Meca500 has 6 joints {} provided".format(len(joints)))
        self.send_string_command(build_command("MoveJoints",joints))
        self.update_log_for_motion_commands()
        

    def MoveLin(self, position, orientation):
        """
        Call the MoveLine Motion Command
        position: desired position [x,y,z] in [mm]
        orientation: desired euler angle XYZ [alpha,beta,gamma] in [deg]
        this methods does not check the response
        """
        if not len(position)==3:
            raise ValueError("RobotController::MoveLin position must have len=3, {} provided".format(len(position)))
        if not len(orientation)==3:
            raise ValueError("RobotController::MoveLin orientation must have len=3, {} provided".format(len(orientation)))
        
        args = list(position)
        args.extend(orientation)
        self.send_string_command(build_command("MoveLin",args))
        self.update_log_for_motion_commands()

    def MoveLinRelTRF(self, position, orientation):
        """
        Call the MoveLinRelTRF Motion Command
        position: desired position [x,y,z] in [mm]
        orientation: desired euler angle XYZ [alpha,beta,gamma] in [deg]
        this methods does not check the response
        """
        if not len(position)==3:
            raise ValueError("RobotController::MoveLinRelTRF position must have len=3, {} provided".format(len(position)))
        if not len(orientation)==3:
            raise ValueError("RobotController::MoveLinRelTRF orientation must have len=3, {} provided".format(len(orientation)))
        
        args = list(position)
        args.extend(orientation)
        self.send_string_command(build_command("MoveLinRelTRF",args))
        self.update_log_for_motion_commands()

    def MoveLinRelWRF(self, position, orientation):
        """
        Call the MoveLinRelWRF Motion Command
        position: desired position [x,y,z] in [mm]
        orientation: desired euler angle XYZ [alpha,beta,gamma] in [deg]
        this methods does not check the response
        """
        if not len(position)==3:
            raise ValueError("RobotController::MoveLinRelWRF position must have len=3, {} provided".format(len(position)))
        if not len(orientation)==3:
            raise ValueError("RobotController::MoveLinRelWRF orientation must have len=3, {} provided".format(len(orientation)))
        
        args = list(position)
        args.extend(orientation)
        self.send_string_command(build_command("MoveLinRelWRF",args))
        self.update_log_for_motion_commands()

    def MovePose(self, position, orientation):
        """
        Call the MovePose Motion Command
        position: desired position [x,y,z] in [mm]
        orientation: desired euler angle XYZ [alpha,beta,gamma] in [deg]
        this methods does not check the response
        """
        if not len(position)==3:
            raise ValueError("RobotController::MovePose position must have len=3, {} provided".format(len(position)))
        if not len(orientation)==3:
            raise ValueError("RobotController::MovePose orientation must have len=3, {} provided".format(len(orientation)))
        
        args = list(position)
        args.extend(orientation)
        self.send_string_command(build_command("MovePose",args))
        self.update_log_for_motion_commands()

    def SetAutoConf(self,e):
        """
        Call the SetAutoConf Motion Command
        this methods does not check the response
        """
        if e is not 0 and e is not 1:
            raise ValueError("RobotController::SetAutoConf invalid value e={}".format(e))
        self.send_string_command(build_command("SetAutoConf",[e]))
        self.update_log_for_motion_commands()

    def SetBlending(self,p):
        """
        Call the SetBlending Motion Command
        this methods does not check the response
        """
        if not (p>=0 and p<=100):
            raise ValueError("RobotController::SetBlending invalid value p={}".format(p))
        self.send_string_command(build_command("SetBlending",[p]))
        self.update_log_for_motion_commands()

    def SetCartAcc(self,p):
        """
        Call the SetCartAcc Motion Command
        this methods does not check the response
        """
        if not (p>1 and p<=100):
            raise ValueError("RobotController::SetCartAcc invalid value p={}".format(p))
        self.send_string_command(build_command("SetCartAcc",[p]))
        self.update_log_for_motion_commands()

    def SetCartAngVel(self,omega):
        """
        Call the SetCartAngVel Motion Command
        this methods does not check the response
        """
        if not (omega>=0.001 and omega<=180):
            raise ValueError("RobotController::SetCartAngVel invalid value omega={}".format(omega))
        self.send_string_command(build_command("SetCartAngVel",[omega]))
        self.update_log_for_motion_commands()

    def SetCartLinVel(self,v):
        """
        Call the SetCartLinVel Motion Command [mm/s]
        this methods does not check the response
        """
        if not (v>=0.001 and v<=500): 
            raise ValueError("RobotController::SetCartLinVel invalid value v={}".format(v))
        self.send_string_command(build_command("SetCartLinVel",[v]))
        self.update_log_for_motion_commands()

    def SetConf(self,c1,c3,c5):
        """
        Call the SetConf Motion Command
        this methods does not check the response
        """
        if c1 is not -1 and c1 is not 1:
            raise ValueError("RobotController::SetConf invalid value c1={}".format(c1))
        if c3 is not -1 and c3 is not 1:
            raise ValueError("RobotController::SetConf invalid value c3={}".format(c3))
        if c5 is not -1 and c5 is not 1:
            raise ValueError("RobotController::SetConf invalid value c5={}".format(c5))
        self.send_string_command(build_command("SetConf",[c1,c3,c5]))
        self.update_log_for_motion_commands()
        
    def SetJointAcc(self,p):
        """
        Call the SetJointAcc Motion Command
        this methods does not check the response
        """
        if not (p>=1 and p<=100):
            raise ValueError("RobotController::SetJointAcc invalid value p={}".format(p))
        self.send_string_command(build_command("SetJointAcc",[p]))
        self.update_log_for_motion_commands()

    def SetJointVel(self,p):
        """
        Call the SetJointVel Motion Command
        this methods does not check the response
        """
        if not (p>=0 and p<=100):
            raise ValueError("RobotController::SetJointVel invalid value p={}".format(p))
        self.send_string_command(build_command("SetJointVel",[p]))
        self.update_log_for_motion_commands()

    def SetTRF(self, origin, orientation):
        """
        Call the SetTRF Motion Command
        origin: desired frame origin [x,y,z] in [mm]
        orientation: desired frame orientation - euler angle XYZ [alpha,beta,gamma] in [deg]
        this methods does not check the response
        """
        if not len(origin)==3:
            raise ValueError("RobotController::SetTRF origin must have len=3, {} provided".format(len(origin)))
        if not len(orientation)==3:
            raise ValueError("RobotController::SetTRF orientation must have len=3, {} provided".format(len(orientation)))
        
        args = list(origin)
        args.extend(orientation)
        self.send_string_command(build_command("SetTRF",args))
        self.update_log_for_motion_commands()

    def SetWRF(self, origin, orientation):
        """
        Call the SetWRF Motion Command
        origin: desired frame origin [x,y,z] in [mm]
        orientation: desired frame orientation - euler angle XYZ [alpha,beta,gamma] in [deg]
        this methods does not check the response
        """
        if not len(origin)==3:
            raise ValueError("RobotController::SetWRF origin must have len=3, {} provided".format(len(origin)))
        if not len(orientation)==3:
            raise ValueError("RobotController::SetWRF orientation must have len=3, {} provided".format(len(orientation)))
        
        args = list(origin)
        args.extend(orientation)
        self.send_string_command(build_command("SetWRF",args))
        self.update_log_for_motion_commands()

