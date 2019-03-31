/************************ fwi84.c *****************************/

/*    Fwi84 is a collection of subroutines used to calculate the
      indices in the Canadian Forest Fire Weather Index (FWI) 
      system.

      Van Wagner.  1985.  Equations and FORTRAN Program for the Canadian 
         Forest Fire Weather Index System.  Can. For. Serv. Ottawa, 
         Ont.  For Tech. Rep. 33.  18 p.

      Variable names and equation numbers are consistent with those 
      used in the FWI document. 

      Functions are set up with all necessary input values as function 
      parameters.  The function returns the new value of the index.

      Variables used in the calls are as follows


      Noon Weather Values:
         T   Temperature (oC)
         H   Humidity (%)
         W   Wind Speed (km/hr)
         ro  Past 24 hour rainfall (mm)
         I   Month (Jan=1, etc.)

      Indices:
         F   Fine Fuel Moisture Code
         Fo  Yesterday's Fine Fuel Moisture Code
         P   Duff Moisture Code
         Po  Yesterday's Duff Moisture Code
         D   Drought Code
         Do  Yesterday's Drought Code
         R   Initial Spread Index
         U   Buildup Index
         S   Fire Weather Index

*/

double FFMCcalc(double T, double H, double W, double ro, double Fo);
double DMCcalc(double T, double H, double ro, double Po, int I);
double DCcalc(double T, double ro, double Do, int I);
double ISIcalc(double F, double W);
double BUIcalc(double P, double D);
double FWIcalc(double R, double U);
double DSRcalc(double S);
