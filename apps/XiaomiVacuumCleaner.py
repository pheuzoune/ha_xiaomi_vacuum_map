import appdaemon.plugins.hass.hassapi as hass
import time
import os
import io
import glob
import shutil
from PIL import Image, ImageDraw, ImageChops

class MapBuilder(hass.Hass):
    print_debug = True
    started = False
    vacuum_host = None
    loop_handle = None
    working_directory = '/dev/shm/xiaomi_vacuum_map'
    slam_files = []


    def initialize(self):
        self.vacuum_host = self.args["xiaomi_vacuum_host"]
        self.vacuum_map_generated = self.args["xiaomi_vacuum_map_generated"]
        self.vacuum_map_base = self.args["xiaomi_vacuum_map_base"]
        self.listen_state(self.state_changed, "vacuum.xiaomi_vacuum_cleaner")


    def state_changed(self, entity, attribute, old, new, args):
        self.debug('vacuum changed state old: '+ old + ' new: '+new)
        if new != 'docked' and not self.started:
            self.debug('got out from dock and main loop is not started')
            self.main_loop()

    def main_loop(self, kwargs=None):
        self.debug('iteration')
        self.rsync_files()
        self.started = True

        list_ppm_file = glob.glob(self.working_directory+'/navmap*.ppm')
        try:
            latest_ppm_file = max(list_ppm_file, key=os.path.getctime)
        except:
            self.run_in(self.main_loop, 2)


        '''
        SLAM file is truncated during cleanup when it's too big
        we'll archive file at each iteration
        If first line of current file is different than first line of last archived file:
            a new archive file is created
        '''
        if len(self.slam_files) == 0:
            #No slam files initiated
            shutil.copy(self.working_directory+'/SLAM_fprintf.log', self.working_directory+'/0_SLAM_fprintf.log')
            self.slam_files.append('0_SLAM_fprintf.log')
        else:
            slam_files_size = len(self.slam_files)
            with open(self.working_directory+'/'+self.slam_files[slam_files_size - 1]) as last_slam_data:
                last_slam_first_line = last_slam_data.readline()
            with open(self.working_directory+'/SLAM_fprintf.log') as current_slam_data:
                current_slam_first_line = current_slam_data.readline()
            if last_slam_first_line != current_slam_first_line:
                self.slam_files.append(str(slam_files_size)+'_SLAM_fprintf.log')

            last_slam_file_position = len(self.slam_files) - 1
            #copying current slam to last in table
            shutil.copy(self.working_directory+'/SLAM_fprintf.log', self.working_directory+'/' + str(last_slam_file_position) +'_SLAM_fprintf.log')

        if os.path.exists(self.working_directory+'/slam_concatenated.log'):
            os.remove(self.working_directory+'/slam_concatenated.log')
        for slam_file in self.slam_files:
            os.system('cat '+ self.working_directory + '/' + slam_file + ' >> ' + self.working_directory + '/slam_concatenated.log')
        slam_file = self.working_directory+'/slam_concatenated.log'
        try:
            self.build_map(slam_file, latest_ppm_file, self.vacuum_map_base, self.vacuum_map_generated)
        except:
            self.debug('Error in map generation')

        '''
        Run the main loop again while vacuum is not docked
        '''
        if self.get_state('vacuum.xiaomi_vacuum_cleaner') != 'docked':
            self.run_in(self.main_loop, 2)
        else:
            self.end_loop()

    def end_loop(self):
        self.started = False
        self.slam_files = []
        shutil.rmtree(self.working_directory)
        self.debug('finishing main loop')


    def rsync_files(self):
        '''
        We cannot determine ppm name, so copying everything that looks like it
        And SLAM_fprintf.log
        '''
        sync_files_cmd  = 'rsync -az --timeout 10 '
        sync_files_cmd += '--include="navmap*.ppm" '
        sync_files_cmd += '--include="SLAM_fprintf.log" '
        sync_files_cmd += '--exclude="*" '
        sync_files_cmd += 'root@' + self.vacuum_host + ':/run/shm/ '
        sync_files_cmd += self.working_directory+ '/ '
        self.debug(sync_files_cmd)
        os.system(sync_files_cmd)



    def build_map(self, slam_file, vacuum_file, backgroung_file, output_file):

        """
        Parameters !
        """
        input_vacuum_x = self.get_state('input_number.vacuum_mapbuilder_dock_x')
        input_vacuum_y = self.get_state('input_number.vacuum_mapbuilder_dock_y')
        input_ratio = self.get_state('input_number.vacuum_mapbuilder_ratio')
        input_rotation = self.get_state('input_number.vacuum_mapbuilder_rotation')

        vacuum_x = int(float(input_vacuum_x)) if input_vacuum_x else 0
        vacuum_y = int(float(input_vacuum_y)) if input_vacuum_y else 0
        ratio = float(input_ratio) if input_ratio and float(input_ratio) > 0 else 1
        rotation = float(input_rotation) if input_rotation else 0

        vacuum_path_color = (0, 0, 255, 255)
        vacuum_surface_color = (0, 0, 255, 70)
        vacuum_position_color = (0, 255, 0, 255)

        """
        nothing to modify after that
        """

        vacuum_image = Image.open(io.BytesIO(open(vacuum_file, 'rb').read()))
        vacuum_image = vacuum_image.convert('RGBA')

        background_image = Image.open(io.BytesIO(open(backgroung_file,'rb').read()))
        background_image = background_image.convert('RGBA')

        slam_log_data = open(slam_file).read()



        def ellipsebb(x, y):
            return x-3*ratio, y-3*ratio, x+3*ratio, y+3*ratio

        #Colors needed to modify vacuum_map
        white = (255,255,255,255)
        grey = (125, 125, 125, 255)  # background color
        transparent = (0, 0, 0, 0)


        # calculate center of the image
        center_x = vacuum_image.size[0] / 2
        center_y = vacuum_image.size[1] / 2

        # crop image to remove extra space
        bgcolor_image = Image.new('RGBA', vacuum_image.size, grey)
        cropbox = ImageChops.subtract(vacuum_image, bgcolor_image).getbbox()
        vacuum_image = vacuum_image.crop(cropbox)

        # Replace grey and white background with transparent pixels
        pixdata = vacuum_image.load()
        for y in range(vacuum_image.size[1]):
            for x in range(vacuum_image.size[0]):
                if pixdata[x, y] == grey or pixdata[x, y] == white:
                    pixdata[x, y] = transparent


        # resize based on ratio to match the background image
        vacuum_image_new_width = int(vacuum_image.size[0] * ratio)
        vacuum_image_new_heigh = int(vacuum_image.size[1] * ratio)
        vacuum_image = vacuum_image.resize((vacuum_image_new_width,vacuum_image_new_heigh), Image.NEAREST)


        # Parameters to upscale Image
        # 20 is the factor to fit coordinates in the standard map, multiplied by ratio
        # to match the background image
        slam_position_factor = 20 * ratio
        # 6 is original size of vacuum in the map
        vacuum_width = int(6 * ratio)

        #Adjust center based on cropbox and ratio
        center_x = int((center_x - cropbox[0]) * ratio)
        center_y = int((center_y - cropbox[1]) * ratio)


        # prepare for drawing
        draw = ImageDraw.Draw(vacuum_image)

        # loop each line of slam log to draw vacuum surface

        for action in ('surface', 'path') :
            prev_pos = None
            for line in slam_log_data.split("\n"):
                # find positions in slamlog
                if 'estimate' in line:
                    d = line.split('estimate')[1].strip()
                    # extract x & y
                    x, y, z = map(float, d.split(' '))
                    # set x & y by center of the image
                    # y is inverted, explaining the minus in front of it
                    x = center_x + (x * slam_position_factor)
                    y = center_y + (-y * slam_position_factor)
                    pos = (x, y)
                    if prev_pos:
                        if action == 'surface':
                            draw.line([prev_pos, pos], vacuum_surface_color, vacuum_width)
                            draw.ellipse(ellipsebb(x, y), vacuum_surface_color)
                        if action == 'path':
                            draw.line([prev_pos, pos], vacuum_path_color,3)
                    prev_pos = pos

        # draw current position
        draw.ellipse(ellipsebb(x, y), vacuum_position_color)

        # crop image
        bgcolor_image = Image.new('RGBA', vacuum_image.size, grey)
        cropbox = ImageChops.subtract(vacuum_image, bgcolor_image).getbbox()

        offset_x = -int((vacuum_image.size[0] / 2 - vacuum_x))
        offset_y = -int((vacuum_image.size[1] / 2 - vacuum_y))
        offset_x = vacuum_x - center_x
        offset_y = vacuum_y - center_y

        vacuum_image = vacuum_image.rotate(rotation)

        background_image.paste(vacuum_image, (offset_x,offset_y), vacuum_image)

        #vacuum_image.paste(background_image)
        temp = io.BytesIO()
        background_image.save(temp, format="png")
        open(output_file, 'wb').write(temp.getvalue())






    def debug(self, message):
        if self.print_debug:
            print('XiaomiVacuumCleaner/MapBuilder: ' + message)
