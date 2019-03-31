SEV Plumerise Module
BlueSky Framework README File


PURPOSE

    This module calculates the plume rise of fire emissions using a Fire Radiative Power (FRP)-based model.
    The module alse requires knowledge of local meteorological data.


SETUP

    setup.ini
    This line will need to be added to your setup file:
        PLUME_RISE=SEVPlumeRise

    This module also requires met data, which you will have to provide for your specific situation, along with this line in the setup.ini file:
        inputs=$MET StandardFiles


REFERENCES

    ORIGIN
    The original journal article building the logic for this model was:
    M. Sofiev, T. Ermakova, and R. Vankevich. "Evaluation of the smoke-injection height from wild-land fires using remote-sensing data" Atmos. Chem. Phys., 12, 1995–2006, 2012. www.atmos-chem-phys.net/12/1995/2012/

    AUTHORS
    M. Sofiev, T. Ermakova, and R. Vankevich (SEV)

    DETAILS
    If an FRP value is not given for a fire, a default value is approximated by averaging the max values of a known dataset:
        http://www.gmes-atmosphere.eu/d/services/gac/nrt/fire_radiative_power
