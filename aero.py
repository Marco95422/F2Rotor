""" 
File: aero.py
Author: Daniele Trincone & Ciro Cuozzo
Creation Date: May 21, 2024

This code calculates the aerodynamic parameters of a chosen station on the blade through a Python class.
Within the class there are functions capable of calculating the Cl_alpha, the alpha_zl, the Cl and the Cd for any 
chosen station.
Three methods are implemented for calculating the coefficients:

- Flatplate method where the aerodynamics is given by Cl = Cl_alpha * alpha with Cl_alpha = 2*pi, and Cd = 0.02;

- xFoil method which calls the xFoil software on the known stations and interpolates in order to obtain the aerodynamic 
  parameters for each station of the blade;

- xRotor method, which uses xRotor aerodynamics by giving certain aerodynamic parameters as input.


"""

## The class must have, as attributes, the Alpha0lift, the Clalpha, the Cl and Cd at the particular lift coefficient.
import os
import subprocess
import numpy as np
import matplotlib.pyplot as plt
import math
from ambiance import Atmosphere
from scipy.interpolate import interp1d, interp2d
import shutil

os.system('cls')

class Aerodynamics():
    def __init__(self, aero_method, alpha_vec_xFoil = None, M_corr = False, Rey_corr = False):
        self.aero_method = aero_method
        self.M_corr = M_corr
        self.Rey_corr = Rey_corr
        if self.aero_method == 'xFoil':
            self.alpha_vec = alpha_vec_xFoil
            
    def aero_database_generator(self, Re_ref, airfoils_folder):
        if not os.path.exists(airfoils_folder):
            print("airfoils_folder does not exist.")
            return None
        
        # Count .txt files in the airfoils folder
        file_coord = [file for file in os.listdir(airfoils_folder) if file.endswith('.txt')]
    
        Cl_database = np.full((len(file_coord),len(self.alpha_vec)),np.nan)
        Cd_database = np.full((len(file_coord),len(self.alpha_vec)),np.nan)
        for i in range(len(file_coord)):
            print(f'Currently generating aerodynamic database for airfoil {i+1}...')
            if os.path.exists(f'airfoil_polar{i+1}.dat'): os.remove(f'airfoil_polar{i+1}.dat')
            for j,alpha in enumerate(self.alpha_vec):
                self.xfoil_run(file_coord[i], Re_ref, alpha,i)

            polar_i=np.loadtxt(f'airfoil_polar{i+1}.dat',skiprows=12)
            Cl_database[i,:] = np.interp(self.alpha_vec, polar_i[:,0], polar_i[:,1]) # Constant extrapolation
            Cd_database[i,:] = np.interp(self.alpha_vec, polar_i[:,0], polar_i[:,2]) # Constant extrapolation
            # f_Cl_database = interp1d(polar_i[:,0], polar_i[:,1], kind='linear', fill_value='extrapolate')
            # Cl_database[i, :] = f_Cl_database(self.alpha_vec)
            # f_Cd_database = interp1d(polar_i[:,0], polar_i[:,1], kind='linear', fill_value='extrapolate')
            # Cd_database[i, :] = f_Cd_database(self.alpha_vec)
            self.Cl_database = Cl_database
            self.Cd_database = Cd_database
        return Cl_database, Cd_database
    
    def eval_lift_properties(self, Cl_database = None, r_R = None, x = None, 
                             M = None,
                             alpha_0_lift = None, 
                             Cl_alpha = None
                             ):
        """Function to evaluate alpha_0_lift and Cl_alpha from either the flat plate model or the xFoil polar:"""
        if M > 0.7:
            print("\nWarning: The mach number is higher than 0.7. It will lead to overestimated lift capabilities.\n")

        if self.aero_method == 'flat_plate':
            Cl_alpha = np.deg2rad(2*math.pi) # Cl = Cl_a*a 
            alpha_0_lift = 0

        elif self.aero_method == 'xFoil':
            f_cl = interp2d(self.alpha_vec,r_R, Cl_database, kind='linear')
            # Points to interpolate
            Cl_alpha = (f_cl(2, x)[0] - f_cl(-2, x)[0])/(2-(-2))
            # Interpolation on 0
            Cl = []
            alpha_0_lift_vec_interp = np.linspace(-6,6,10)
            for alpha in alpha_0_lift_vec_interp:
                Cl.append(f_cl(alpha, x)[0])
    
            alpha_0_lift = np.interp(0, Cl, alpha_0_lift_vec_interp)                                                          # deg

        elif self.aero_method == 'xRotor':
            if self.aero_method == 'xRotor' and (Cl_alpha == None or alpha_0_lift == None):
                raise ValueError("if xRotor is used as aero method, all aerodynamic parameters must be provided as input (Read doc)!")
            Cl_alpha = np.deg2rad(Cl_alpha)
            # alpha_0_lift = alpha_0_lift
        else:
            raise ValueError("'aero_method' must be 'flat_plate', 'xFoil' or 'xRrotor'.")
        
        if self.M_corr:
            Cl_alpha /=  math.sqrt(1-M**2)

        return np.rad2deg(Cl_alpha), np.deg2rad(alpha_0_lift)                                                 # Cl_alpha in 1/rad, alpha_0_lift in rad          
    
    def eval_coeffs(self, AoA, Re_ref, Re, M, x = None, r_R = None, Cl_database = None, Cd_database = None,
                    alpha_0_lift = None,                    
                    Cl_alpha = None,                        
                    Cl_alpha_stall = None,                  
                    Cl_max = None,
                    Cl_min = None,
                    Cl_incr_to_stall = None,
                    Cd_min = None,
                    Cl_at_cd_min = None,
                    dCd_dCl2 = None,
                    Mach_crit = None,
                    Re_scaling_exp = None,
                    ):
        """Function to evaluate Cl and Cd at the given AoA from either flat plate model, xRotor model or the xFoil polar"""

        if self.aero_method == 'flat_plate':
            Cl_alpha = 2*math.pi
            lift_coeff = min(Cl_alpha*AoA/math.sqrt(1-M**2), 3.5)     
            lift_coeff = max(lift_coeff, -3.5)      # using Cl_alpha = 2pi, stall at Cl = 1.5
            drag_coeff = 0.0200                                         # Default

        elif self.aero_method == 'xFoil':
            if self.aero_method == 'xFoil' and any(var is None for var in [self.alpha_vec, x, r_R, Cl_database, Cd_database]):
                raise ValueError("if xfoil is used as aero method, all aerodynamic parameters must be provided as input (Read doc)!")
            f_cl = interp2d(self.alpha_vec, r_R, Cl_database, kind='linear')
            f_cd = interp2d(self.alpha_vec, r_R, Cd_database, kind='linear')
            # Points to interpolate
            lift_coeff = f_cl(AoA, x)[0]
            drag_coeff = f_cd(AoA, x)[0]

        elif self.aero_method == 'xRotor':
            if self.aero_method == 'xRotor' and any(var is None for var in [Cl_alpha, alpha_0_lift, Cl_alpha_stall, Cl_max, Cl_min, Cl_incr_to_stall, Cd_min, Cl_at_cd_min, dCd_dCl2, Mach_crit, Re_scaling_exp]):
                raise ValueError("if xRotor is used as aero method, all aerodynamic parameters must be provided as input (Read doc)!")
            # ------------------------- Lift coefficient --------------------------#

            CDMSTALL  =  0.1000
            CDMFACTOR = 10.0
            CLMFACTOR =  0.25
            MEXP      =  3.0
            CDMDD     =  0.0020
            PG = 1/math.sqrt(1-M**2)
            lift_coeff = Cl_alpha * PG * (AoA - alpha_0_lift)

            # --- Effective CLmax is limited by Mach effects ---

            DMSTALL = (CDMSTALL / CDMFACTOR) ** (1.0 / MEXP)
            CLMAXM = max(0.0, (Mach_crit + DMSTALL - M) / CLMFACTOR) + Cl_at_cd_min
            CLMAX = min(Cl_max, CLMAXM)
            CLMINM = min(0.0, -(Mach_crit + DMSTALL - M) / CLMFACTOR) + Cl_at_cd_min
            CLMIN = max(Cl_min, CLMINM)

            # --- CL limiter function (turns on after +-stall) ---

            ECMAX = math.exp(min(200.0, float((lift_coeff - CLMAX) / Cl_incr_to_stall)))
            ECMIN = math.exp(min(200.0, float((CLMIN - lift_coeff) / Cl_incr_to_stall)))
            CLLIM = Cl_incr_to_stall * math.log((1.0 + ECMAX) / (1.0 + ECMIN))

            # --- Subtract off a (nearly unity) fraction of the limited CL function ---

            FSTALL = Cl_alpha_stall / Cl_alpha
            lift_coeff = lift_coeff - (1.0 - FSTALL) * CLLIM

            # ------------------------- Drag coefficient --------------------------#
            if Re <= 0:
                RCORR = 1.0
            else:
                RCORR = (Re / Re_ref) ** Re_scaling_exp
            # --- Drag parabolic in the linear lift range ---

            drag_coeff = (Cd_min + dCd_dCl2 * (lift_coeff - Cl_at_cd_min) ** 2) * RCORR

            # --- Post Stall Drag ---

            FSTALL = Cl_alpha_stall / Cl_alpha
            DCDX = (1.0 - FSTALL) * CLLIM / (PG * Cl_alpha)
            DCD = 2.0 * DCDX ** 2

            # --- Compressibility Drag ---

            DMDD = (CDMDD / CDMFACTOR) ** (1.0 / MEXP)
            CRITMACH = Mach_crit - CLMFACTOR * abs(lift_coeff - Cl_at_cd_min) - DMDD       
            if M < CRITMACH:
                CDC = 0.0
            else:
                CDC = CDMFACTOR * (M - CRITMACH) ** MEXP

            FAC = 1.0     
            # Although test data does not show profile drag increases due to Mach #
            # you could use something like this to add increase drag by Prandtl-Glauert
            # (or any function you choose)
            # FAC = PG

            # Total drag terms

            drag_coeff = FAC * drag_coeff + DCD + CDC

        if self.aero_method != 'xRotor':
            if Re < 1e+5:
                f = -0.4                                    # Empirical factor for Reynolds number correction
            elif Re >= 1e+5 and Re < 1e+6:
                f = -1
            else:
                f = -0.15
                
            if self.Rey_corr:
                drag_coeff *= (Re/Re_ref)**f    
            if self.M_corr:
                lift_coeff /=  math.sqrt(1-M**2)      
            
        return lift_coeff, drag_coeff
    
    def xfoil_run(self, file_coord, Re, alpha,  i, n_iter = 50, airfoil_folder = 'airfoil_input'):
        """Function to call xFoil"""
        #xfoil_path = 'airfoil_input/xfoil.exe'
        #xfoil_path = os.path.join(airfoil_folder, 'xfoil.exe')
        xfoil_path = 'xfoil.exe'
        # Write xfoil command file
        XfoilCmd_fileName = 'Xfoil_cmd.inp'
        with open(XfoilCmd_fileName, 'w') as f:
            f.write('PLOP\n') 
            f.write('G\n\n')  
            # Load coordinates
            f.write(f'load {airfoil_folder}\{file_coord}\n')
            # Set the number of panels
            f.write('ppar\n')  
            f.write('N\n')
            f.write('160\n\n\n')
            # Close TE
            f.write('gdes\n')  
            f.write('tgap\n')  
            f.write('0\n')     
            f.write('0.2\n')   
            f.write('exec gset\n\n')  
            # Set Re and M
            f.write('oper\n')
            f.write('Re\n')
            f.write(f'{Re}\n')
            f.write('M\n') 
            f.write('0\n') # Incompressible analysis
            f.write('v\n') # Viscous analysis
            # Change number of iterations
            f.write('iter\n')
            f.write('%d\n' % n_iter)
            # Polar accumulation
            f.write('pacc\n')
            f.write(f'airfoil_polar{i+1}.dat\n\n')
            f.write('a\n')
            f.write(f'{alpha}\n')
            f.write('pacc\n\n')
            f.write('quit\n')
            
        # Execute xfoil
        cmd = f'"{xfoil_path}" < Xfoil_cmd.inp > xfoil.out'
        try:
            subprocess.run(cmd, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            print('Xfoil execution failed:', e)
            return [float('NaN')]
        

####################### THE FOLLOWING PART IS JUST AN EXAMPLE OF HOW TO USE IT. IT MUST BE COMMENTED ########################
'''
How to Instantiate the class: 
aero_method = 'flat_plate' or 'xFoil' or 'xRotor'
if aero_method == 'xFoil':
        aero = aero.Aerodynamics(aero_method = aero_method,
                            alpha_vec_xFoil=np.arange(-25,25,1),
                            M_corr = True,
                            Rey_corr = True) 
        aero.Cl_database, aero.Cd_database = aero.aero_database_generator(Re_ref = 1e+6, airfoils_folder = 'airfoil_input')
else: 
    aero = aero.Aerodynamics(aero_method = aero_method,
                 M_corr = True,
                 Rey_corr = True)


## --------------------- HOW TO COMPUTE Cl alpha and alpha zero lift --------------------- ##

    if aero.aero_method == 'xRotor':
        cla, bo = aero.eval_lift_properties(M = Vr/a_sound, alpha_0_lift = np.deg2rad(0), Cl_alpha = 6.28)
    elif aero.aero_method == 'xFoil':
        cla, bo = aero.eval_lift_properties(Cl_database = aero.Cl_database, r_R = geom.r_R_known, x = x, M = Vr/a_sound)
    else:
        cla, bo = aero.eval_lift_properties(M = Vr/a_sound)

## --------------------- HOW TO COMPUTE Cl and Cd --------------------- ##
    if aero.aero_method == 'xRotor': 
        cl, cd = aero.eval_coeffs(Re_ref =1e+6 ,Re =Vr*chord/ni ,M = Vr/a_sound,AoA=alpha,
                              alpha_0_lift = np.deg2rad(0), Cl_alpha = 6.28, 
                              Cl_alpha_stall = 0.100, Cl_max = 1.5, Cl_min = -0.5, Cl_incr_to_stall = 0.100,
                              Cd_min = 0.0130, Cl_at_cd_min = 0.500, dCd_dCl2 = 0.004, Mach_crit = 0.8, Re_scaling_exp = -0.15
                              )
        
    elif aero.aero_method == 'xFoil':
        cl, cd = aero.eval_coeffs(AoA = np.rad2deg(alpha), Re_ref = 1e+6, Re =Vr*chord/ni, M = Vr/a_sound, x = x, r_R = geom.r_R_known, Cl_database = aero.Cl_database, Cd_database = aero.Cd_database)
 
    else:
        cl, cd = aero.eval_coeffs(Re_ref =1e+6 ,Re =Vr*chord/ni ,M = Vr/a_sound,AoA=alpha)
'''
