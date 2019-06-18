import socket
import time

class MecademicRobot:
    """Class for the MecademicRobot allowing for communication with the 
    Mecademic Robot with all of its features available

    Attributes:
        Address: IP Address
        HTTPAddress: http:// + IPAddress
        socket: socket connecting to physical Meca500
        End of Block: Setting for EOB reply
        End of Movement: Setting for EOM reply
        Error: Error Status of the Meca500
        Motion Error : Flag for Motion Error
    """
    #constructor
    #scan for firmware version and saves to variable
    def __init__(self, address):
        """Constructor for an instance of the Class Meca500 

        :param address: The IP address associated to the Meca500
        """
        self.address = address
        self.httpAddress = 'http://'+self.address
        self.socket = None
        self.EOB = 1
        self.EOM = 1
        self.error = False
        self.motionError = False

    #Return is an error has been encountered and the Robot is in error state
    def isInError(self):
        """Status method that checks whether the Meca500 is in error mode.
        Returns 1 for error and 0 otherwise.

        :return error: Returns the error flag
        """
        return self.error               #return the global variable error, which is updated by the other methods

    #Resets the robot error status
    def ResetError(self):
        """Resets the error in the Meca500 
        """
        self.error = False
        cmd = "ResetError"
        response = self.exchangeMsg(cmd)
        reset_success = self._response_contains(response, ["The error was reset","There was no error to reset"])
        if reset_success:
            self.error = False
        else:
            self.error = True
        return response

    #connect to robot through socket
    def Connect(self):
        """Connects Meca500 object communication to the physical Meca500
        Returns the status of the connection, true for success, false for failure

        :return status: Return whether the connection is established
        """
        try:
            self.socket = socket.socket()                   #Get a socket
            self.socket.settimeout(0.1)                     #set the timeout to 100ms
            try:
                self.socket.connect((self.address, 10000))  #connect to the robot's address
            except socket.timeout:                          #catch if the robot is not connected to in time
                raise TimeoutError                          
            # Receive confirmation of connection
            if self.socket is None:                         #check that socket is not connected to nothing
                raise RuntimeError
            self.socket.settimeout(10)                      #set timeout to 10 seconds
            try:    
                response = self.socket.recv(1024).decode("ascii")   #receive message from robot
            except socket.timeout:
                raise RuntimeError
            response_found = self._response_contains(response, ["[3000]"])  #search for key [3000] in the received packet
            if not response_found:
                raise RuntimeError
            else:
                return response_found                       #return if key was found in packet
        except TimeoutError:
            print("Timed out while try to connect to Robot, verify connections and ports")
            return False
        # OTHER USER !!!
        except RuntimeError:
            print("Other User connected to Robot, verify connections")
            return False

    #Looks through string to find desired pattern
    @staticmethod
    def _response_contains(response, code_list):
        """Scans received response for code IDs

        :param response: Message to scan for codes
        :param code_list: List of codes to look for in the response
        :return response_found: Returns whether the response contains a code ID of interest 
        """
        response_found = False
        for code in code_list:
            if response.find(code) != -1:
                response_found = True
                break
        return response_found
    
    #Disconnect from socket
    def Disconnect(self):
        """Disconnects Meca500 object from physical Meca500
        """
        if(self.socket is not None):
            self.socket.close()
            self.socket = None

    #send message to the robot
    def _send(self, cmd):
        """Sends a command to the physical Meca500

        :param cmd: Command to be sent  (string)
        :return status: Returns whether the message is sent (boolean)
        """
        if self.socket is None or self.error:               #check that the connection is established or the robot is in error
            return False                                    #if issues detected, no point in trying to send a cmd that won't reach the robot
        cmd = cmd + '\0'
        status = 0
        while status == 0:
            try:                                  #while the message hasn't been sent
                status = self.socket.send(cmd.encode("ascii"))  #send command in ascii encoding
            except:
                break
            if status != 0:
                return True                                 #return true when the message has been sent 
        print("Could not send to Robot, verify connection") #Message failed to be sent, return false
        return False        

    #receive message from the robot
    def _receive(self, answer_list, delay):
        """Receives message from the Meca500 and 
        looks for expected answer in the reply

        :param answer_list: codes to look for in the response (list)
        :param delay: time to set for timeout of the socket (int)
        :return response: Response received from Meca500 (string)
        """
        if self.socket is None:                         #check that the connection is established
            return                                      #if no connection, nothing to receive
        response_list = []                              
        response_found = False
        for x in answer_list:                           #convert codes to search for in answer into comparable format
            response_list.append("["+str(x)+"]")
        error_found = False
        error_list = ["["+str(i)+"]" for i in range(1000, 1039)]+["["+str(i)+"]" for i in [3001,3003,3005,3009,3014,3026]]  #Make error codes in a comparable format
        self.socket.settimeout(delay)                   #set read timeout to desired delay
        while not response_found and not error_found:   #while no answers have been received, keep looking
            try:
                response = self.socket.recv(1024).decode("ascii")   #read message from robot
            except socket.timeout:
                return                                  #if timeout reached, either connection lost or nothing was sent from robot (damn disabled EOB and EOM)
            if(len(response_list)!=0):                  #if the message has a code to look for, find them
                response_found = self._response_contains(response, response_list)
            error_found = self._response_contains(response, error_list) #search message for errors
        if error_found:                                 #if errors have been found, flag the script
            self.error = True
            if self._response_contains(response,['3005']):
                self.motionError = True
        return response                                 #return the retrieved message

    #exchange message between the CPU and the robot
    def exchangeMsg(self, cmd, delay = 20, decode=True):
        """Sends and receives with the Meca500

        :param cmd: Command to send to the Meca500  (string)
        :param delay: timeout to set for the socket (int)
        :return response: Response with desired code ID (string)
        """
        response_list = self._getAnswerList(cmd)
        if(not self.error):                                 #if there is no error
            status = self._send(cmd)                        #send the command to the robot
            if status is True:                           #if the command was sent
                answer = self._receive(response_list, delay)#get response from robot
                if answer is not None:                      #if message was retrieved
                    for response in response_list:          #search for response codes
                        if self._response_contains(answer, [str(response)]): 
                            if(decode):
                                return self._decodeMsg(answer, response)   #decrypt response based on right response code
                            else:
                                return answer
                    error_list = [str(i) for i in range(1000, 1039)]+[str(i) for i in [3001,3003,3005,3009,3014,3026]]  #Make error codes in a comparable format
                    for response in error_list:
                        if self._response_contains(answer, [str(response)]): 
                            if(decode):
                                return self._decodeMsg(answer, response)   #decrypt response based on right response code
                            else:
                                return answer
                else:
                    if(len(response_list) == 0):            #if we aren't expecting anything, don't bother looking
                        return
                    else:
                        print('Not getting response from Meca500')
                        return

            print("Restablishing connection")               #if message didn't send correctly, reboot communication
            self.Disconnect()
            time.sleep(1)
            self.Connect()
            return

    #convert the command into the proper format. Format : Command_name(arg0,arg1,...,arg_n)
    def _buildCommand(self, cmd, arg_list = []):
        """Builds the command string to send to the Meca500
        from the function name and arguments the command needs

        :param cmd: command name to send to the Meca500
        :param arg_list: list of arguments the command requires
        :return command: final command for the Meca500
        """
        command = cmd
        if(len(arg_list)!=0):
            command = command + '('
            for index in range(0, (len(arg_list)-1)):
                command = command+str(arg_list[index])+','
            command = command+str(arg_list[-1])+')'
        return command

    #decrypt the received message from the robot into a usable tuple
    def _decodeMsg(self,response, response_key):
        """Decrypt information from the Meca500 response to useful information
        that can be manipulated

        :param response: Response from the Meca500
        :param response_key: Code ID of response to decrypt
        :return code: Decrypted information
        """
        code = response.replace("["+str(response_key)+"][", "").replace("]", "").replace("\x00", "")    #remove delimiters and \x00 bytes
        code_list = code.split(",")                         #split packets into their individual selves
        if(response_key == 2026 or response_key == 2027):   #if expected packet is from GetJoints (2026) or GetPose (2027), rest of packet is position data 
            code_list_float = tuple((float(x) for x in code_list))      #convert position data to floats
            return code_list_float
        elif(response_key == 2029 or response_key == 2007 or response_key == 2079): #if expected packet is from GetConf (2029), GetStatusRobot (2007) or GetStatusGripper (2079), rest of packet is data
            code_list_int = tuple((int(x) for x in code_list))          #convert status data into integers
            return code_list_int
        else:
            return code                                      #nothing to decrypt or decryption not specified

    #retrieves the expected answer codes from the Meca500 to look for
    def _getAnswerList(self, command):
        """Retrieve the expected answer codes that the Meca500 should send as feedback after
        a command.

        :param command: command that is to be sent to the Meca500 (string)
        :return answer_list: list of answer codes to search for in response (list)
        """
        if(command.find('ActivateRobot') != -1):
            return [2000,2001]
        elif(command.find('ActivateSim')!= -1):
            return [2045]
        elif(command.find('ClearMotion')!= -1):
            return [2044]
        elif(command.find("DeactivateRobot")!= -1):
            return [2004]
        elif(command.find("BrakesOn")!= -1):
            return [2010]
        elif(command.find("BrakesOff")!= -1):
            return [2008]
        elif(command.find("GetConf")!= -1):
            return [2029]
        elif(command.find('GetJoints')!= -1):
            return [2026]
        elif(command.find('GetStatusRobot')!= -1):
            return [2007]
        elif(command.find('GetStatusGripper')!= -1):
            return [2079]
        elif(command.find('GetPose')!= -1):
            return [2027]
        elif(command.find('Home')!= -1):
            return [2002,2003]
        elif(command.find('PauseMotion')!= -1):
            answer_list = [2042]
            if(self.EOM == 1): 
                answer_list.append(3004)
            return answer_list
        elif(command.find('ResetError')!= -1):
            return [2005,2006]
        elif(command.find('ResumeMotion')!= -1):
            return [2043]
        elif(command.find('SetEOB')!= -1):
            return [2054,2055]
        elif(command.find('SetEOM')!= -1):
            return [2052,2053]
        else:
            answer_list = []
            if(self.EOB==1):
                answer_list.append(3012)
            if(self.EOM==1):
                for name in ['MoveJoints','MoveLin','MoveLinRelTRF','MoveLinRelWRF','MovePose','SetCartAcc','SetJointAcc','SetTRF','SetWRF']:
                    if(command.find(name) != -1):
                        answer_list.append(3004)
                        break
            return answer_list

    #Activate robot
    def Activate(self):
        """Activates the Meca500 

        :return response: Returns receive decrypted response
        """
        cmd = "ActivateRobot"
        return self.exchangeMsg(cmd)

    #Deactivate robot
    def Deactivate(self):
        """Deactivates the Meca500 

        :return response: Returns receive decrypted response
        """
        cmd = "DeactivateRobot"
        return self.exchangeMsg(cmd)

    #Toggles the robot Simulation mode
    def SimulationMode(self, state):
        """Changes the Meca500 simulation mode 

        :param state: State of simulation (ON or OFF)
        :return response: Returns receive decrypted response
        """
        if(state == 1 or state == 'ON' or state == 'activate'):
            cmd = "ActivateSim"
            return self.exchangeMsg(cmd)
        else:
            cmd = "DeactivateSim"
            return self.exchangeMsg(cmd)

    #Put robot into EtherCat mode
    def EtherCatMode(self):
        """Places the Meca500 in EtherCat mode
        """
        cmd = "SwitchToEtherCAT"
        return self.exchangeMsg(cmd)
    
    #Toggle the End of Block response from the robot
    def SetEOB(self, e):
        """Sets End of Block answer active or inactive in the Meca500

        :param e: Enables (1) EOB or Disables (0) EOB
        :return response: Returns receive decrypted response
        """
        if(e == 1):
            self.EOB = 1
        else:
            self.EOB = 0
        raw_cmd = "SetEOB"
        cmd = self._buildCommand(raw_cmd,[e])
        return self.exchangeMsg(cmd)
        
    #Toggle the End of movement response from the robot
    def SetEOM(self, e):
        """Sets End of Movement answer active or inactive in the Meca500

        :param e: Enables (1) EOM or Disables (0) EOM
        :return response: Returns receive decrypted response
        """
        if(e == 1):
            self.EOM = 1
        else:
            self.EOM = 0
        raw_cmd = "SetEOM"
        cmd = self._buildCommand(raw_cmd,[e])
        return self.exchangeMsg(cmd)    

    #Home the robot
    def Home(self):
        """Homes the Meca500

        :return response: Returns receive decrypted response
        """
        cmd = "Home"
        return self.exchangeMsg(cmd)

    #Make the robot wait a certain period of time
    def Delay(self, t):
        """Gives the Meca500 a wait time before performing another action

        :return response: Returns receive decrypted response
        """
        if(not isinstance(t,float)):
            t = float(t)
        raw_cmd = "delay"
        cmd = self._buildCommand(raw_cmd,[t])
        return self.exchangeMsg(cmd, t*2)

    #Make the robot move to a certain position based on the angles of the robots joints
    def MoveJoints(self, theta_1, theta_2, theta_3, theta_4, theta_5, theta_6):
        """Moves the joints of the Meca500 to the desired angles
        
        :param theta_1: Angle of joint 1
        :param theta_2: Angle of joint 2
        :param theta_3: Angle of joint 3
        :param theta_4: Angle of joint 4
        :param theta_5: Angle of joint 5
        :param theta_6: Angle of joint 6
        :return response: Returns receive decrypted response
        """
        raw_cmd = "MoveJoints"
        cmd = self._buildCommand(raw_cmd,[theta_1,theta_2,theta_3,theta_4,theta_5,theta_6])
        return self.exchangeMsg(cmd)

    #Make the robot move in a line to a certain position
    def MoveLin(self, x, y, z, alpha, beta, gamma):
        """Moves the Meca500 tool reference in a straight line to final
        point with specified direction

        :param x: Final x coordinate
        :param y: Final y coordinate
        :param z: Final z coordinate
        :param alpha: Final Alpha angle
        :param beta: Final Beta angle
        :param gamma: Final Gamma angle
        :return response: Returns receive decrypted response
        """
        raw_cmd = "MoveLin"
        cmd = self._buildCommand(raw_cmd,[x,y,z,alpha,beta,gamma])
        return self.exchangeMsg(cmd)

    #Make the robot move in a line to a certain position based off the TRF reference frame    
    def MoveLinRelTRF(self, x, y, z, alpha, beta, gamma):
        """Moves the Meca500 tool reference frame to specified coordinates and heading

        :param x: New Reference x coordinate
        :param y: New Reference y coordinate
        :param z: New Reference z coordinate
        :param alpha: New Reference Alpha angle
        :param beta: New Reference Beta angle
        :param gamma: New Reference Gamma angle
        :return response: Returns receive decrypted response
        """
        raw_cmd = "MoveLinRelTRF"
        cmd = self._buildCommand(raw_cmd,[x,y,z,alpha,beta,gamma])
        return self.exchangeMsg(cmd)

    #Make the robot move to a certain position
    def MovePose(self, x, y, z, alpha, beta, gamma):
        """Moves the Meca500 joints to have the TRF at (x,y,z)
        with heading (alpha, beta, gamma)

        :param x: Final x coordinate
        :param y: Final y coordinate
        :param z: Final z coordinate
        :param alpha: Final Alpha angle
        :param beta: Final Beta angle
        :param gamma: Final Gamma angle
        :return response: Returns receive decrypted response
        """
        raw_cmd = "MovePose"
        cmd = self._buildCommand(raw_cmd,[x,y,z,alpha,beta,gamma])
        return self.exchangeMsg(cmd)

    #Enables/Disables the robot's blending feature. p ranges from 0 (disabled) to 100
    def SetBlending(self, p):
        """Sets the blending of the Meca500

        :param p: Enable(1-100)/Disable(0) Meca500's blending
        :return response: Returns receive decrypted response
        """
        raw_cmd = "SetBlending"
        cmd = self._buildCommand(raw_cmd,[p])
        return self.exchangeMsg(cmd)

    #Enables or Disables the automatic robot configuration selection and has effect only on the MovePose command, e: enable (1) or disable (0)
    def SetAutoConf(self, e):
        """Enables or Disables the automatic robot configuration 
        selection and has effect only on the MovePose command

        :param e: Enable(1)/Disable(0) Meca500's automatic configuration selection
        :return response: Returns receive decrypted response
        """
        raw_cmd = "SetAutoConf"
        cmd = self._buildCommand(raw_cmd,[e])
        return self.exchangeMsg(cmd)

    #Limits the Cartesian acceleration both linear and angular of the end-effector, p : 1 to 100
    def SetCartAcc(self, p):
        """Sets the cartesian accelerations of the linear and angular movements of the 
        Meca500 end effector

        :param p: value between 1 and 100
        :return response: Returns receive decrypted response
        """
        raw_cmd = "SetCartAcc"
        cmd = self._buildCommand(raw_cmd,[p])
        return self.exchangeMsg(cmd)

    #Limits the angular velocity of the robot TRF with respect to its WRF, w: 0.001 to 180
    def SetCartAngVel(self, w):
        """Sets the cartesian angular velocity of the Meca500 TRF with respect to its WRF

        :param w: value between 0.001 and 180
        :return response: Returns receive decrypted response
        """
        raw_cmd = "SetCartAngVel"
        cmd = self._buildCommand(raw_cmd,[w])
        return self.exchangeMsg(cmd)

    #Limits the Cartesian linear velocity of the robot's TRF with respect to its WRF, v : 0.001 to 500
    def SetCartLinVel(self, v):
        """Sets the cartesian linear velocity of the Meca500's TRF relative to its WRF

        :param v: between 0.001 and 500
        :return response: Returns receive decrypted response
        """
        raw_cmd = "SetCartLinVel"
        cmd = self._buildCommand(raw_cmd,[v])
        return self.exchangeMsg(cmd)

    #Sets the desired robot inverse kinematic configuration to be observed in the MovePose command, c : -1 or 1 
    def SetConf(self, c1, c3, c5):
        """Sets the desired Meca500 inverse kinematic configuration to be observed in the 
        MovePose command

        :param c1: -1 or 1
        :param c3: -1 or 1
        :param c5: -1 or 1
        :return response: Returns received decrypted response
        """
        raw_cmd = "SetConf"
        cmd = self._buildCommand(raw_cmd,[c1,c3,c5])
        return self.exchangeMsg(cmd)
    
    #Limits the velocity of the gripper fingers with respect to the gripper, p : 1 to 100
    def SetGripperVel(self, p):
        """Sets the Gripper fingers' velocity with respect to the gripper

        :param p: value between 1 to 100
        :return response: Returns the decrypted response from the Meca500
        """
        raw_cmd = "SetGripperVel"
        cmd = self._buildCommand(raw_cmd,[p])
        return self.exchangeMsg(cmd)
    
    #Limits the acceleration of the joints, p : 1 to 100
    def SetJointAcc(self, p):
        """Sets the acceleration of the joints

        :param p: value between 1 to 100
        :return response: Returns the decrypted response from the Meca500
        """
        raw_cmd = "SetJointAcc"
        cmd = self._buildCommand(raw_cmd,[p])
        return self.exchangeMsg(cmd)
    
    #Limits the angular velocities of the robot joints, velocity : 1 to 100
    def SetJointVel(self, velocity):
        """Sets the angular velocities of the Meca500's joints

        :param velocity: value between 1 to 100
        :return response: Returns the decrypted response from the Meca500
        """
        raw_cmd = "SetJointVel"
        cmd = self._buildCommand(raw_cmd,[velocity])
        return self.exchangeMsg(cmd)

    #Defines the pose of the TRF with respect to the FRF
    def SetTRF(self, x, y, z, alpha, beta, gamma):
        """Sets the Meca500 TRF at (x,y,z) and heading (alpha, beta, gamma)
        with respect to the FRF

        :param x: Final x coordinate
        :param y: Final y coordinate
        :param z: Final z coordinate
        :param alpha: Final Alpha angle
        :param beta: Final Beta angle
        :param gamma: Final Gamma angle
        :return response: Returns receive decrypted response
        """
        raw_cmd = "SetTRF"
        cmd = self._buildCommand(raw_cmd,[x,y,z,alpha,beta,gamma])
        return self.exchangeMsg(cmd)
    
    #Defines the pose of the WRF with respect to the BRF
    def SetWRF(self, x, y, z, alpha, beta, gamma):
        """Sets the Meca500 WRF at (x,y,z) and heading (alpha, beta, gamma)
        with respect to the BRF

        :param x: Final x coordinate
        :param y: Final y coordinate
        :param z: Final z coordinate
        :param alpha: Final Alpha angle
        :param beta: Final Beta angle
        :param gamma: Final Gamma angle
        :return response: Returns receive decrypted response
        """
        raw_cmd = "SetWRF"
        cmd = self._buildCommand(raw_cmd,[x,y,z,alpha,beta,gamma])
        return self.exchangeMsg(cmd)

    #Sets the cornering of the Meca500 R2
    def SetCornering(self, arg):
        """Sets the cornering of the Meca500 R2 model

        :param arg: value of the cornering
        :return response: Returns the decrypted response from the Meca500
        """
        raw_cmd = "SetCornering"
        cmd = self._buildCommand(raw_cmd,[arg])
        return self.exchangeMsg(cmd)

    #Retrieves the status of the robot
    def GetStatus(self):
        """Retrieves the status of the Meca500 

        :return status: Returns tuple with status of Activation, Homing, Simulation
        Error, Paused, EOB and EOM
        """
        received = None
        while received is None:
            cmd = "GetStatusRobot"
            received = self.exchangeMsg(cmd)
        code_list_int = received
        return {"Activated": code_list_int[0],
                "Homing": code_list_int[1],
                "Simulation": code_list_int[2],
                "Error": code_list_int[3],
                "Paused": code_list_int[4],
                "EOB": code_list_int[5],
                "EOM": code_list_int[6]}
    
    #Retrieves the current inverse kinematic configuration
    def GetConf(self):
        """Retrieves the current inverse kinematic configuration

        :return response: Returns the decrypted response from the Meca500
        """
        cmd = "GetConf"
        return self.exchangeMsg(cmd)

    #Retrieves the robot joint angles in degrees
    def GetJoints(self):
        """Retrieves the Meca500 joint angles in degrees

        :return response: Returns the decrypted response from the Meca500
        """
        cmd = "GetJoints"
        return self.exchangeMsg(cmd)

    #Retrieves the current pose of the robot TRF with respect to the WRF
    def GetPose(self):
        """Retrieves the current pose of the Meca500 TRF with
        respect to the WRF

        :return response: Returns the decrypted response from the Meca500
        """
        cmd = "GetPose"
        return self.exchangeMsg(cmd)

    #Opens the gripper of the end-effector
    def GripperOpen(self):
        """Opens the gripper of the end-effector

        :return response: Returns the decrypted response from the Meca500
        """
        cmd = 'GripperOpen'
        return self.exchangeMsg(cmd)

    #Closes the gripper of the end-effector
    def GripperClose(self):
        """Closes the gripper of the end-effector

        :return response: Returns the decrypted response from the Meca500
        """
        cmd = 'GripperClose'
        return self.exchangeMsg(cmd)

    #Stops the robot movement
    def PauseMotion(self):
        """Stops the robot movement and holds until ResumeMotion

        :return response: Returns the decrypted response from the Meca500
        """
        cmd = "PauseMotion"
        return self.exchangeMsg(cmd)

    #Resumes the robot movement
    def ResumeMotion(self):
        """Resumes the robot movement after being Paused from PauseMotion
        or ClearMotion

        :return response: Returns the decrypted response from the Meca500
        """
        cmd = "ResumeMotion"
        return self.exchangeMsg(cmd)

    #Stops the robot movement and deletes the rest of the robot's trajectory
    def ClearMotion(self):
        """Stops the robot movement and deletes the rest of the robot's
        trajectory. Holds until a ResumeMotion

        :return response: Returns the decrypted response from the Meca500
        """
        cmd = "ClearMotion"
        return self.exchangeMsg(cmd)

    #These commands enables the brakes of joints 1, 2 and 3, if and only if the robotis powered but deactivated.
    def BrakesOn(self):
        """These commands enables the brakes of joints 1, 2 and 3,
        if and only if the robotis powered but deactivated.
        
        :return response: Returns the decrypted response from the Meca500
        """
        cmd = "BrakesOn"
        return self.exchangeMsg(cmd)
    
    #These commands disable the brakes of joints 1, 2 and 3, if and only if the robotis powered but deactivated.
    def BrakesOff(self):
        """These commands disables the brakes of joints 1, 2 and 3,
        if and only if the robotis powered but deactivated.
        
        :return response: Returns the decrypted response from the Meca500
        """
        cmd = "BrakesOff"
        return self.exchangeMsg(cmd)