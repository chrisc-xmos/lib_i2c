# Copyright (c) 2014-2018, XMOS Ltd, All rights reserved
import xmostest
from enum import Enum

VERBOSE = True

class i2c_change(enum.Enum):
    nothing           = 0
    positive_edge_SCL = 1
    negative_edge_SCL = 2
    positive_edge_SDA = 3
    negative_edge_SDA = 4

class I2CMasterChecker(xmostest.SimThread):
    """"
    This simulator thread will act as I2C slave and check any transactions
    caused by the master.
    """

    def __init__(self, scl_port, sda_port, expected_speed,
                 tx_data=[], ack_sequence=[], clock_stretch=0):
        self._scl_port = scl_port
        self._sda_port = sda_port
        self._tx_data = tx_data
        self._ack_sequence = ack_sequence
        self._expected_speed = expected_speed
        self._clock_stretch = clock_stretch

        self._external_scl_value = 0
        self._external_sda_value = 0

        self._scl_change_time = None
        self._sda_change_time = None
        self._last_sda_change_time = None
        self._scl_value = 0
        self._sda_value = 0

	self.last_negative_edge_scl = None
	self.last_positive_edge_scl = None
        self.last_change    = i2c_change.nothing

        self._clock_release_time = None

        self._bit_num = 0
        self._bit_times = []
        self._prev_fall_time = None
        self._byte_num = 0

        self._read_data = None
        self._write_data = None

        self._drive_ack = 1

        print "Checking I2C: SCL=%s, SDA=%s" % (self._scl_port, self._sda_port)

    def error(self, str):
       print "ERROR: %s @ %s" % (str, self.xsi.get_time())

    def info(self, str):
       if VERBOSE:
           print "INFO: %s @ %s" % (str, self.xsi.get_time())

    def read_port(self, port, external_value):
      driving = self.xsi.is_port_driving(port)
      if driving:
        value = self.xsi.sample_port_pins(port)
      else:
        value = external_value
        # Maintain the weak external drive
        self.xsi.drive_port_pins(port, external_value)
      # print "READ {}, got {}, {} ({}) @ {}".format(
      #   port, driving, value, external_value, self.xsi.get_time())
      return value

    def read_scl_value(self):
      return self.read_port(self._scl_port, self._external_scl_value)

    def read_sda_value(self):
      return self.read_port(self._sda_port, self._external_sda_value)

    def drive_scl(self, value):
       # Cache the value that is currently being driven
       self._external_scl_value = value
       self.xsi.drive_port_pins(self._scl_port, value)

    def drive_sda(self, value):
       # Cache the value that is currently being driven
       self._external_sda_value = value
       self.xsi.drive_port_pins(self._sda_port, value)

    def get_next_ack(self):
        if self._ack_index >= len(self._ack_sequence):
            return True
        else:
            ack = self._ack_sequence[self._ack_index]
            self._ack_index += 1
            return ack

    #
    # The following tests are designed to check particular specificiation points
    # in the I2C spec.
    #

    # I2C Spec: test fSCL
    def check_clock_period(self, time):
        if (self._expected_speed == 100 and time < 10000) or\
           (self._expected_speed == 400 and time < 2500):
            self.error("Clock period less than minimum in spec: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("Clock period OK: %g >= 10000 ns" % time)
            if (self._expected_speed == 400):
                self.info("Clock period OK: %g >= 2500 ns" % time)

    # I2C Spec: test tHD;STA
    def check_hold_start_time(self, time):
        if (self._expected_speed == 100 and time < 4000) or\
           (self._expected_speed == 400 and time < 600):
            self.error("Start bit hold time less than minimum in spec: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("Start bit hold time OK: %g >= 4000 ns" % time)
            if (self._expected_speed == 400):
                self.info("Start bit hold time OK: %g >= 600 ns" % time)

    # I2C Spec test tLOW
    def check_clock_low_time(self, time):
        if (self._expected_speed == 100 and time < 4700) or\
           (self._expected_speed == 400 and time < 1300):
            self.error("Clock low time less than minimum in spec: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("Clock low time OK: %g >= 4700 ns" % time)
            if (self._expected_speed == 400):
                self.info("Clock low time OK: %g >= 1300 ns" % time)

    # I2C Spec:test tHIGH
    def check_clock_high_time(self, time):
        if (self._expected_speed == 100 and time < 4000) or\
           (self._expected_speed == 400 and time < 600):
            self.error("Clock high time less than minimum in spec: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("Clock high time OK: %g >= 4000 ns" % time)
            if (self._expected_speed == 400):
                self.info("Clock high time OK: %g >= 600 ns" % time)

    # I2C Spec: test tSU;STA
    def check_setup_start_time(self, time):
        if (self._expected_speed == 100 and time < 4700) or\
           (self._expected_speed == 400 and time < 600):
            self.error("Start bit setup time less than minimum in spec: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("Start bit setup time OK: %g >= 4700 ns" % time)
            if (self._expected_speed == 400):
                self.info("Start bit setup time OK: %g >= 600 ns" % time)

    # I2C Spec: test tHD;DAT
    # If this test fails it indicates a test environment problem
    # Output from the device under test should always be tested by tVD;DAT or tVD;ACK
    # TODO: handle negative hold times up to -300ns as per spec.
    def check_data_hold_time(self, time):
        if (self._expected_speed == 100 and time > 0) or\
           (self._expected_speed == 400 and time > 0):
            self.error("Data hold time not respected: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("Data hold time OK: %g >= 0 ns" % time)
            if (self._expected_speed == 400):
                self.info("Data hold time OK: %g >= 0 ns" % time)

    # I2C Spec: test tSU;DAT
    # If this test fails it indicates a test environment problem
    # Output from the device under test should always be tested by tVD;DAT or tVD;ACK
    def check_data_setup_time(self, time):
        if (self._expected_speed == 100 and time < 250) or\
           (self._expected_speed == 400 and time < 100):
            self.error("Data setup time less than minimum in spec: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("Data setup time OK: %g >= 250 ns" % time)
            if (self._expected_speed == 400):
                self.info("Data setup time OK: %g >= 100 ns" % time)

    # I2C Spec: test tSU;STO
    def check_setup_stop_time(self, time):
        if (self._expected_speed == 100 and time < 4000) or\
           (self._expected_speed == 400 and time < 600):
            self.error("Stop bit setup time less than minimum in spec: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("Stop bit setup time OK: %g >= 4000 ns" % time)
            if (self._expected_speed == 400):
                self.info("Stop bit setup time OK: %g >= 600 ns" % time)

    # I2C Spec: test tBUF
    def check_bus_free_time(self, time):
      """ Check the time from the STOP to the START condition
      """
      if (self._expected_speed == 100 and time < 4700) or \
         (self._expected_speed == 400 and time < 1300):
          self.error("STOP to START time less than minimum in spec: %gns" % time)
      else:
          if (self._expected_speed == 100):
              self.info("STOP to START time OK: %g >= 4700 ns" % time)
          if (self._expected_speed == 400):
              self.info("STOP to START time OK: %g >= 1300 ns" % time)

    # I2C Spec: test tVD;DAT
    def check_data_valid_time(self, time):
        if time < 0:
            # Data change must have been for a previous bit
            return

        if (self._expected_speed == 100 and time > 3450) or\
           (self._expected_speed == 400 and time >  900):
            self.error("Data valid time not respected: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("Data valid time OK: %g <= 3450 ns" % time)
            if (self._expected_speed == 400):
                self.info("Data valid time OK: %g <= 900 ns" % time)

    # I2C Spec: test tVD;ACK
    def check_ack_valid_time(self, time):
        if time < 0:
            # Data change must have been for a previous bit
            return

        if (self._expected_speed == 100 and time > 3450) or\
           (self._expected_speed == 400 and time >  900):
            self.error("ACK valid time not respected: %gns" % time)
	else:
            if (self._expected_speed == 100):
                self.info("ACK valid time OK: %g <= 3450 ns" % time)
            if (self._expected_speed == 400):
                self.info("ACK valid time OK: %g <= 900 ns" % time)


   def do_timing_checks (self):
      #
      # Apply checks. Tests are listed in the order they appear in the
      # I2C specification.
      #

      # fSCL - test against last SCL edge of the same type
      if current_change == i2c_change.negative_edge_SCL and\
         self.last_negative_edge_SCL != None:
      	check_clock_period(self, time_now - self.last_negative_edge_SCL)

      if current_change == i2c_change.positive_edge_SCL and\
         self.last_positive_edge_SCL != None:
      	check_clock_period(self, time_now - self.last_positive_edge_SCL)

      # tHD;STA
      if self.last_change == i2c_change.negative_edge_SCL and\
           current_change == i2c_change.negative_edge_SDA :
        check_hold_start_time(self, time_difference)

      # tHD;STA - Possible negative values
#      if self.last_change == i2c_change.positive_edge_SCL and\
#           current_change == i2c_change.negative_edge_SDA :
          # This condition may indicate an early SDA transition


      # tLOW - test against last SCL edge regardless of SDA
      if current_change == i2c_change.positive_edge_SCL and\
         self.last_negative_edge_SCL != None:
        check_clock_low_time(self, time_now - self.last_negative_edge_SCL)

      # tHIGH - test against last SCL edge regardless of SDA
      if current_change == i2c_change.negative_edge_SCL and\
         self.last_positive_edge_SCL != None:
        check_clock_high_time(self, time_now - self.last_positive_edge_SCL)

      # tSU;STA
      if self.last_change == i2c_change.positive_edge_SCL and\
           current_change == i2c_change.negative_edge_SDA :
        check_setup_start_time(self, time_difference)

      # tHD;DAT
      if self.last_change == i2c_change.negative_edge_SCL and\
          (current_change == i2c_change.negative_edge_SDA or\
           current_change == i2c_change.positive_edge_SDA) :
        check_data_hold_time(self, time_difference)

      # tSU;DAT
      if (self.last_change == i2c_change.positive_edge_SDA  or\
          self.last_change == i2c_change.negative_edge_SDA) and\
            current_change == i2c_change.positive_edge_SCL :
        check_data_setup_time(self, time_difference)

      # tSU;STO
      if self.last_change == i2c_change.positive_edge_SCL and\
           current_change == i2c_change.positive_edge_SDA :
        check_setup_stop_time(self, time_difference)

      # tBUF
      if self.last_change == i2c_change.positive_edge_SDA and\
           current_change == i2c_change.negative_edge_SDA and\
           new_scl_value  == 1:
        check_bus_free_time(self, time_difference)

      # tVD;DAT
      # TODO: identify that this is a data cycle driven by lib_i2c
      if self.last_change == i2c_change.negative_edge_SCL and\
          (current_change == i2c_change.negative_edge_SDA or\
           current_change == i2c_change.positive_edge_SDA) :
        check_data_valid_time(self, time_difference)

      # tVD;ACK
      # TODO: identify that this is an ACK cycle driven by lib_i2c
      if self.last_change == i2c_change.negative_edge_SCL and\
          (current_change == i2c_change.negative_edge_SDA or\
           current_change == i2c_change.positive_edge_SDA) :
        check_ack_valid_time(self, time_difference)





    def get_next_data_item(self):
        if self._tx_data_index >= len(self._tx_data):
            return 0xab
        else:
            data = self._tx_data[self._tx_data_index]
            self._tx_data_index += 1
            return data

    states = {
      #                      EXPECT     |  Next state on transition of
      # STATE            :   SCL,  SDA  |  SCL       SDA
      #

      "STOPPED"          : ( 1,    1,     "ILLEGAL",          "STARTING" ),
      "STARTING"         : ( 1,    0,     "DRIVE_BIT",        "ILLEGAL" ),
      "DRIVE_BIT"        : ( 0,    None,  "SAMPLE_BIT",       "DRIVE_BIT" ),
      "SAMPLE_BIT"       : ( 1,    None,  "DRIVE_BIT",        "CHECK_START_STOP" ),
      "CHECK_START_STOP" : ( 1,    None,  "DRIVE_BIT",        "ILLEGAL" ),
      "BYTE_DONE"        : ( None, None,  "DRIVE_ACK",        "ILLEGAL" ),
      "DRIVE_ACK"        : ( 0,    None,  "SAMPLE_ACK",       "DRIVE_ACK" ),
      "ACK_SENT"         : ( 0,    None,  "SAMPLE_ACK",       "ACK_SENT" ),
      # This state will be transitioned by the handler
      "SAMPLE_ACK"       : ( 1,    None,  "NOT_POSSIBLE",     "NOT_POSSIBLE" ),
      "ACKED"            : ( None, None,  "DRIVE_BIT",        "ACKED" ),
      # After a NACK, the master must generate a Stop or Repeated Start
      "NACKED"           : ( None, None,  "NACKED_SELECT",    "ILLEGAL" ),
      "NACKED_SELECT"    : ( 0,    1,     "STOPPED",          "STOPPING_0" ),
      "STOPPING_0"       : ( 0,    0,     "STOPPING_1",       "ILLEGAL" ),
      "STOPPING_1"       : ( 1,    0,     "ILLEGAL",          "STOPPED" ),
      "REPEAT_START"     : ( 0,    1,     "ILLEGAL",          "STARTING" ),
      "ILLEGAL"          : ( None, None,  "ILLEGAL",          "ILLEGAL" ),
    }

    @property
    def expected_scl(self):
      return self.states[self._state][0]

    @property
    def expected_sda(self):
      return self.states[self._state][1]

    def wait_for_stopped(self):
      while self._scl_value != 1 or self._sda_value != 1:
        self.wait_for_port_pins_change([self._scl_port, self._sda_port])
        self._scl_value = self.read_scl_value()
        self._sda_value = self.read_sda_value()

    def wait_for_change(self):
      """ Wait for either the SDA/SCL port to change and return which one it was.
          Need to also maintain the drive of any value set by the user.
      """
      scl_changed = False
      sda_changed = False

      scl_value = self._scl_value
      sda_value = self._sda_value

      # The value might already not be the same if both signals transitioned
      # simultaneously previously
      new_scl_value = self.read_scl_value()
      new_sda_value = self.read_sda_value()
      while new_scl_value == scl_value and new_sda_value == sda_value:
        if self._clock_release_time is not None:
          # When clock stretching it is necessary simply to clock the simulation
          # as there is no wait for data change with timeout
          self.wait_for_next_cycle()
          if self.xsi.get_time() >= self._clock_release_time:
            self.drive_scl(1)
            self._clock_release_time = None
            if VERBOSE:
              print "End clock stretching @ {}".format(self.xsi.get_time())

        else:
          # Default case, simply wait for one of the pins to change
          self.wait_for_port_pins_change([self._scl_port, self._sda_port])

        new_scl_value = self.read_scl_value()
        new_sda_value = self.read_sda_value()

      time_now = self.xsi.get_time()

      if VERBOSE:
        print "wait_for_change {},{} -> {},{} @ {}".format(
          scl_value, sda_value, new_scl_value, new_sda_value, time_now)


      #
      # SCL changed
      #
      if scl_value != new_scl_value:
	if (new_scl_value == 0):
	  self.info("SCL Negedge")
          current_change = i2c_change.negative_edge_SCL
	else:
	  self.info("SCL Posedge")
          current_change = i2c_change.positive_edge_SCL

      #
      # SDA changed
      #
      if sda_value != new_sda_value:
	if (new_sda_value == 0):
	  self.info("SDA Negedge")
          current_change = i2c_change.negative_edge_SDA
	else:
	  self.info("SDA Posedge")
          current_change = i2c_change.positive_edge_SDA

      time_difference = time_now - self.last_change_time


      #
      # update record of previous transitions
      #
      self.last_change_time = time_now
      self.last_change      = current_change

      if current_change == i2c_change.negative_edge_SCL:
        if self.last_negative_edge_SCL != None:
          self._bit_times.append(time_now - self.last_negative_edge_SCL)
	self.last_negative_edge_SCL = time_now


      if current_change == i2c_change.positive_edge_SCL:
	self.last_positive_edge_scl = time_now

      if current_change == i2c_change.positive_edge_SCL or\
         current_change == i2c_change.negative_edge_SCL:
        self._scl_change_time = time_now
        self._scl_value = new_scl_value


      #
      # SCL changed
      #
      if scl_value != new_scl_value:
        scl_changed = True

        # Stretch the clock if required
        if self._clock_stretch and new_scl_value == 0:
          self.drive_scl(0)
          self._clock_release_time = time_now + self._clock_stretch
          if VERBOSE:
            print "Start clock stretching @ {}".format(self.xsi.get_time())

      #
      # SDA changed - don't detect simultaneous changes and have the clock
      # be higher priority if they do.
      #
      if not scl_changed and (sda_value != new_sda_value):
        sda_changed = True

      return scl_changed, sda_changed

    def set_state(self, next_state):
      if VERBOSE:
        print "State: {} -> {} @ {}".format(self._state, next_state, self.xsi.get_time())
      self._prev_state = self._state
      self._state = next_state

      # Ensure the current state of the SCL/SDA is valid
      self.check_scl_sda_lines()

      # Execute the handler for the state
      handler = getattr(self, "handle_" + self._state.lower())
      handler()

    def move_to_next_state(self, scl_changed, sda_changed):
      if scl_changed:
        next_state = self.states[self._state][2]
      else:
        next_state = self.states[self._state][3]
      self.set_state(next_state)

    def check_value(self, value, expected, name):
      if expected is not None:
        if value != expected:
          self.error("{}: {} != {}".format(self._state, name, expected))

    def check_scl_sda_lines(self):
      self.check_value(self.read_scl_value(), self.expected_scl, "SCL")
      self.check_value(self.read_sda_value(), self.expected_sda, "SDA")

    def start_read(self):
      self._bit_num = 0
      self._bit_times = []
      self._prev_fall_time = None
      self._read_data = 0
      self._write_data = None

    def start_write(self):
      self._bit_num = 0
      self._bit_times = []
      self._prev_fall_time = None
      self._read_data = None
      self._write_data = self.get_next_data_item()

    def byte_done(self):
      if self._read_data is not None:
        print("Byte received: 0x%x" % self._read_data)
        self._drive_ack = 1
      else:
        # Reads are acked by the master
        self._drive_ack = 0
        print("Byte sent")

      if self._bit_times:
        avg_bit_time = sum(self._bit_times) / len(self._bit_times)
        speed_in_kbps = pow(10, 6) / avg_bit_time
        print "Speed = %d Kbps" % int(speed_in_kbps + .5)
        if self._expected_speed != None and \
          (speed_in_kbps < 0.99 * self._expected_speed):
           print "ERROR: speed is <1% slower than expected"

        if self._expected_speed != None and \
          (speed_in_kbps > self._expected_speed * 1.05):
           print "ERROR: speed is faster than expected"

      if self._byte_num == 0:
        # Command byte

        # The command is always acked by the slave
        self._drive_ack = 1

        # Determine whether it is starting a read or write
        mode = self._read_data & 0x1
        print("Master %s transaction started, device address=0x%x" %
              ("write" if mode == 0 else "read", self._read_data >> 1))

        if mode == 0:
          self.start_read()
        else:
          self.start_write()

      else:
        if self._read_data is not None:
          self.start_read()

      self.set_state("BYTE_DONE")

    #
    # Handler functions for each state
    #
    def handle_stopped(self):
      pass

    def handle_starting(self):
      print("Start bit received")
      self._byte_num = 0
      self.start_read()
      if self._last_sda_change_time is not None:
        self.check_bus_free_time(self.xsi.get_time() - self._last_sda_change_time)

    def handle_drive_bit(self):
      if self._write_data is not None:
        # Drive data being read by master
        self.drive_sda((self._write_data & 0x80) >> 7)
      else:
        # Simulate external pullup
        self.drive_sda(1)

    def handle_sample_bit(self):
      if self._read_data is not None:
        # Ensure that the data setup time has been respected
        self.check_data_setup_time(self.xsi.get_time() - self._sda_change_time)

        # Read the data value
        self._read_data = (self._read_data << 1) | self.read_sda_value()

      if self._write_data is not None:
        self._write_data = (self._write_data << 1) & 0xff

      self._bit_num += 1
      if self._bit_num == 8:
        self.byte_done()

    def handle_check_start_stop(self):
      if self._sda_value:
        if self._bit_num != 1:
          self.error("Stopping when mid-byte")
        self.set_state("STOPPED")
      else:
        if self._bit_num != 1:
          self.error("Start bit detected mid-byte")
        self.set_state("STARTING")

    def handle_byte_done(self):
      pass

    def handle_drive_ack(self):
      if self._drive_ack:
        ack = self.get_next_ack()
        if ack:
          print("Sending ack")
          self.drive_sda(0)
        else:
          print("Sending nack")
          self.drive_sda(1)
        self.set_state("ACK_SENT")
      else:
        # Simulate external pullup
        self.drive_sda(1)

    def handle_ack_sent(self):
      pass

    def handle_sample_ack(self):
      if self._drive_ack:
        if self.xsi.is_port_driving(self._sda_port):
          print("WARNING: master driving SDA during ACK phase")

        if self.read_sda_value():
          self.set_state("NACKED")
        else:
          self.set_state("ACKED")

      else:
        nack = self.read_sda_value()
        print("Master sends %s." % ("NACK" if nack else "ACK"));
        if nack:
          self.set_state("NACKED")
          print("Waiting for stop/start bit")
        else:
          self.set_state("ACKED")
          # Prepare the next byte to be read
          self._write_data = self.get_next_data_item()

      self._bit_num = 0
      self._byte_num += 1

    def handle_acked(self):
      pass

    def handle_nacked(self):
      pass

    def handle_nacked_select(self):
      # Simulate external pullup
      self.drive_sda(1)

    def handle_stopping_0(self):
      pass

    def handle_stopping_1(self):
      print("Stop bit received");

    def handle_repeat_start(self):
      print("Repeated start bit received")

    def handle_illegal(self):
      self.error("Illegal state arrived at from {}".format(self._prev_state))

    def run(self):
      # Simulate external pullup
      self.drive_scl(1)
      self.drive_sda(1)

      # Ignore the blips on the ports at the start
      self.wait_until(100)
      self._scl_value = self.read_scl_value()
      self._sda_value = self.read_sda_value()

      self.wait_for_stopped()

      self._tx_data_index = 0
      self._ack_index = 0

      self._state = "STOPPED"

      while True:
        scl_changed, sda_changed = self.wait_for_change()

        if scl_changed and sda_changed:
          self.error("Unsupported having SCL & SDA changing simultaneously")

        self.move_to_next_state(scl_changed, sda_changed)
