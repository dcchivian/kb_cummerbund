import sys
import os
import json
import re
import io
import urllib
import hashlib
import string
import random
import requests
import math
import logging
import shutil
import time
import traceback
from requests_toolbelt import MultipartEncoder
from multiprocessing import Pool
#from functools import partial
import subprocess
from zipfile import ZipFile
from os import listdir
from os.path import isfile, join, exists
import tarfile
import script_util
try:
    from biokbase.HandleService.Client import HandleService
except:
    from biokbase.AbstractHandle.Client import AbstractHandle as HandleService

from biokbase.workspace.client import Workspace

import biokbase.Transform.script_utils as script_utils

import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()
import filter_expression as f


def id_generator(size=8, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))
    
def parse_expression_matrix_separate_comma(infile):
    outfile = infile + ".parse.txt"
    fp=open(outfile, "w")
    with open(infile) as f:
        newmatrix = []
        for line in f:
            genes  = line.split("\t",1)[0]
            genes = genes.strip('"')
            values = line.split("\t",1)[1:]
            for gene in genes.split(","):
                    newval = gene + "\t" + "\t".join(values)
                    fp.write(newval)
    f.close()
    fp.close()
    return  outfile



def get_command_line_heatmap_basic(rparams):

#TODO: Check existence of files and directories
    ropts            = ["Rscript", rparams['plotscript']]

    try:
        ropts.append("--genelist")
        ropts.append(rparams['genelist'])
    except:
        ropts.append("nogenelist")
       
    ropts.append("--cuffdiff")
    ropts.append(rparams['cuffdiff_dir'])
        
    ropts.append("--outpng")
    ropts.append(rparams['outpng'])

    ropts.append("--imageheight")
    ropts.append(rparams['imageheight'])
    
    ropts.append("--imagewidth")
    ropts.append(rparams['imagewidth'])

    ropts.append("--include_replicates")
    ropts.append(rparams['include_replicates'])

    ropts.append("--outmatrix")
    ropts.append(rparams['outmatrix'])

    ropts.append("--pairs")
    ropts.append(rparams['pairs'])

    ropts.append("--logMode")
    ropts.append(rparams['logMode'])

    ropts.append("--removezeroes")
    ropts.append(rparams['removezeroes'])



    
    roptstr = " ".join(str(x) for x in ropts)
    
    return roptstr
    
    
    






def untar_files(logger, src_fn, dst_path):
    """
    Extract all index files into an output zip file on disk.
    """

    #Check if file exists.
    if exists(src_fn) == False:
        logger.info("Tar file does not exists")
        return False

    # Open archive
    tar = tarfile.open(src_fn)

    # Extract archive
    tar.extractall(dst_path)
    tar.close()

    return True

def rplotandupload (logger, scratch, rscripts, plotscript, shock_url, hs_url, token, cummerbundplotset, title, description, cuffdiff_dir):
    """
    Prepare URIs and call R script to generate image, json files.
    Upload the generated image and json files to Shock
    Get Shock handles and prepare cummerbundplotset object and append
        to user provided list.
    """

    #Check if data directory exists.
    if exists(cuffdiff_dir) == False:
        logger.info("Cuffdiff directory does not exists")
        return False

    # Generated image location
    outpng           = join(scratch,  plotscript) + ".png"
    #Need to check if its already present
    if exists(outpng):
        logger.info("PNG file already exists")
        return False

    # Generated json location
    outjson          = join(scratch,  plotscript) + ".json"
    #Need to check if its already present
    if exists(outjson):
        logger.info("JSON file already exists")
        return False

    # Location of the R script to be executed
    computescript    = join(rscripts, plotscript)
    #Check if it exists
    if exists(computescript) == False:
        logger.info("R script does not exists")
        return False

    # Generate command to be executed.
    ropts            = ["Rscript", computescript]

    ropts.append("--cuffdiff_dir")
    ropts.append(cuffdiff_dir)

    ropts.append("--outpng")
    ropts.append(outpng)

    ropts.append("--outjson")
    ropts.append(outjson)


    # Make call to execute the system.
    roptstr = " ".join(str(x) for x in ropts)
    openedprocess = subprocess.Popen(roptstr, shell=True, stdout=subprocess.PIPE)
    openedprocess.wait()
    #Make sure the openedprocess.returncode is zero (0)
    if openedprocess.returncode != 0:
        logger.info("R script did not return normally, return code - "
            + str(openedprocess.returncode))
        return False

    # Upload image file and get the shock handle
    png_handle = script_util.create_shock_handle( logger,
       outpng, shock_url, hs_url, "png", token )
    #Check for the return value and if error take measure.
    if png_handle["id"] == "":
        logger.info("Could not create Shock handle")
        return False

   #TODO Removed all json handle related stuff. fix it later
    # Upload json file and get the shock handle
   # json_handle = script_util.create_shock_handle( logger,
   #    outjson, shock_url, hs_url, "json", token )
    #Check for the return value and if error take measure.
  #  if json_handle["id"] == "":
   #     logger.info("Could not create Shock handle")
    #    return False

    # Create a return list
    #TODO fix this "png_json_handle"  : json_handle,
    cummerbundplot = {
        "png_handle"       : png_handle,
        "plot_title"       : title,
        "plot_description" : description
    }
    cummerbundplotset.append(cummerbundplot)

    return True


def rplotanduploadinteractive (system_params, fparams, rparams, roptstr):
    """
    Prepare URIs and call R script to generate image, json files.
    Upload the generated image and json files to Shock
    Get Shock handles and prepare cummerbundplotset object and append
        to user provided list.
    """
    logger      = system_params['logger']
    scratch     = system_params['scratch']
    shock_url   = system_params['shock_url']
    hs_url      = system_params['hs_url']
    ws_url      = system_params['ws_url']
    token       = system_params['token']
    workspace   = system_params['workspace']
    rscripts   = system_params['rscripts']


    logger=system_params['logger']



    #Check if data directory exists.
#    if exists(cuffdiff_dir) == False:
#        logger.info("Cuffdiff directory does not exists")
#        return False

#    # Generated image location
#    outpng           = join(scratch,  plotscript) + ".png"
#    #Need to check if its already present
#    if exists(outpng):
#        logger.info("PNG file already exists")
#        return False

#    # Generated json location
#    outjson          = join(scratch,  plotscript) + ".json"
#    #Need to check if its already present
#    if exists(outjson):
#        logger.info("JSON file already exists")
#        return False


    logger.info(roptstr)
    openedprocess = subprocess.Popen(roptstr, shell=True, stdout=subprocess.PIPE)
    openedprocess.wait()
    #Make sure the openedprocess.returncode is zero (0)
    if openedprocess.returncode != 0:
        logger.info("R script did not return normally, return code - " + str(openedprocess.returncode))
        return False

    # Upload image file and get the shock handle
#    png_handle = script_util.create_shock_handle( logger,
#       rparams['outpng'], system_params['shock_url'], system_params['hs_url'], "png", system_params['token'] )
    #Check for the return value and if error take measure.
#    if png_handle["id"] == "":
#        logger.info("Could not create Shock handle")
#        return False

   #TODO Removed all json handle related stuff. fix it later
    # Upload json file and get the shock handle
   # json_handle = script_util.create_shock_handle( logger,
   #    outjson, shock_url, hs_url, "json", token )
    #Check for the return value and if error take measure.
  #  if json_handle["id"] == "":
   #     logger.info("Could not create Shock handle")
    #    return False

    # Create a return list
    #TODO fix this "png_json_handle"  : json_handle,
    TSV_to_FeatureValue = "trns_transform_TSV_Exspression_to_KBaseFeatureValues_ExpressionMatrix"

    outmatrix =  rparams['outmatrix']
        #outmatrixparse =  join (scratch, scriptfile) + ".matrix.parse.txt"
    outjson =      "out.json"

    matrix_parse = parse_expression_matrix_separate_comma(outmatrix)

    cmd_expression_json = [TSV_to_FeatureValue,
               '--workspace_service_url', ws_url,
               '--workspace_name', workspace,
               '--object_name', matrix_parse,
               '--working_directory', scratch,
               '--input_directory', scratch,
               '--output_file_name', outjson ]

    cmd_expression_json = ["perl", '/kb/module/lib/kb_cummerbund/get_exp_matrix.pl', '/kb/module/work/outmatrix.parse.txt', '/kb/module/work/out.json'] 
    logger.info (" ".join(cmd_expression_json))
    tool_process = subprocess.Popen (" ".join (cmd_expression_json), stderr=subprocess.PIPE, shell=True)
    stdout, stderr = tool_process.communicate()
#    os.remove(matrix_parse)

    if stdout is not None and len(stdout) > 0:
            logger.info(stdout)
    if stderr is not None and len(stderr) > 0:
            logger.info(stderr)

    if tool_process.returncode != 0:
           return False
    return outjson





def rplotandupload2 (system_params, fparams, rparams, roptstr):
    """
    Prepare URIs and call R script to generate image, json files.
    Upload the generated image and json files to Shock
    Get Shock handles and prepare cummerbundplotset object and append
        to user provided list.
    """
    logger      = system_params['logger']
    scratch     = system_params['scratch']
    shock_url   = system_params['shock_url']
    hs_url      = system_params['hs_url']
    ws_url      = system_params['ws_url']
    token       = system_params['token']
    workspace   = system_params['workspace']
    rscripts   = system_params['rscripts']


    logger=system_params['logger']



    #Check if data directory exists.
#    if exists(cuffdiff_dir) == False:
#        logger.info("Cuffdiff directory does not exists")
#        return False

#    # Generated image location
#    outpng           = join(scratch,  plotscript) + ".png"
#    #Need to check if its already present
#    if exists(outpng):
#        logger.info("PNG file already exists")
#        return False

#    # Generated json location
#    outjson          = join(scratch,  plotscript) + ".json"
#    #Need to check if its already present
#    if exists(outjson):
#        logger.info("JSON file already exists")
#        return False


    logger.info(roptstr)
    openedprocess = subprocess.Popen(roptstr, shell=True, stdout=subprocess.PIPE)
    openedprocess.wait()
    #Make sure the openedprocess.returncode is zero (0)
    if openedprocess.returncode != 0:
        logger.info("R script did not return normally, return code - " + str(openedprocess.returncode))
        return False

    # Upload image file and get the shock handle
    png_handle = script_util.create_shock_handle( logger,
       rparams['outpng'], system_params['shock_url'], system_params['hs_url'], "png", system_params['token'] )
    #Check for the return value and if error take measure.
    if png_handle["id"] == "":
        logger.info("Could not create Shock handle")
        return False

   #TODO Removed all json handle related stuff. fix it later
    # Upload json file and get the shock handle
   # json_handle = script_util.create_shock_handle( logger,
   #    outjson, shock_url, hs_url, "json", token )
    #Check for the return value and if error take measure.
  #  if json_handle["id"] == "":
   #     logger.info("Could not create Shock handle")
    #    return False

    # Create a return list
    #TODO fix this "png_json_handle"  : json_handle,
    cummerbundplot = {
        "png_handle"       : png_handle,
        "plot_title"       : fparams['title'],
        "plot_description" : fparams['description']
    }
    fparams['cummerbundplotset'].append(cummerbundplot)
    TSV_to_FeatureValue = "trns_transform_TSV_Exspression_to_KBaseFeatureValues_ExpressionMatrix"

    outmatrix =  rparams['outmatrix']
        #outmatrixparse =  join (scratch, scriptfile) + ".matrix.parse.txt"
    outjson =      "out.json"




    matrix_parse = parse_expression_matrix_separate_comma(outmatrix)

    cmd_expression_json = [TSV_to_FeatureValue,
               '--workspace_service_url', ws_url,
               '--workspace_name', workspace,
               '--object_name', matrix_parse,
               '--working_directory', scratch,
               '--input_directory', scratch,
               '--output_file_name', outjson ]

    cmd_expression_json = ["perl", '/kb/module/lib/kb_cummerbund/get_exp_matrix.pl', '/kb/module/work/outmatrix.parse.txt', '/kb/module/work/out.json'] 
    logger.info (" ".join(cmd_expression_json))
    tool_process = subprocess.Popen (" ".join (cmd_expression_json), stderr=subprocess.PIPE, shell=True)
    stdout, stderr = tool_process.communicate()
#    os.remove(matrix_parse)

    if stdout is not None and len(stdout) > 0:
            logger.info(stdout)
    if stderr is not None and len(stderr) > 0:
            logger.info(stderr)

    if tool_process.returncode != 0:
           return False
    return outjson




def extract_cuffdiff_data (logger, shock_url, scratch, s_res, user_token):

        returnVal = False
       # Get input data Shock Id and Filename.
        cuffdiff_shock_id = s_res[0]['data']['file']['id']
        cuffdiff_file_name = s_res[0]['data']['file']['file_name']


        filesize = None

        dx = script_util.download_file_from_shock( logger,
            shock_url, cuffdiff_shock_id, cuffdiff_file_name,
            scratch, filesize, user_token)

        #cuffdiff_file_name =None

        #Decompress tar file and keep it in a directory
        zipfile = join(scratch, cuffdiff_file_name)
        dstnExtractFolder1 = join(scratch, "cuffdiffData")
        dstnExtractFolder = join(dstnExtractFolder1, "cuffdiff")

        if not os.path.exists(dstnExtractFolder):
            os.makedirs(dstnExtractFolder)

        #untarStatus = untar_files(logger, tarfile, dstnExtractFolder)
        #if untarStatus == False:
        #    logger.info("Problem extracting the archive")
        #    return returnVal
        unzipStatus = script_util.unzip_files(logger, zipfile, dstnExtractFolder)
        if unzipStatus == False:
            logger.info("Problem extracting the archive")
            return returnVal


        foldersinExtractFolder = os.listdir(dstnExtractFolder)

        if len(foldersinExtractFolder) == 0:
            logger.info("Problem extracting the archive")
            return returnVal

        # Run R script to run cummerbund json and update the cummerbund output json file
        cuffdiff_dir = dstnExtractFolder

        return cuffdiff_dir





def generate_and_upload_expression_matrix (logger, scratch, rscripts, scriptfile, shock_url, hs_url, token, cuffdiff_dir, ws_url, workspace):
        TSV_to_FeatureValue = "trns_transform_TSV_Exspression_to_KBaseFeatureValues_ExpressionMatrix"
        returnVal = False
        if exists(cuffdiff_dir) == False:
            logger.info("Cuffdiff directory does not exist")
            return False

        #generate expression matrix
        #input = Rscript fpkmgenematrix.R cuffdiff_dir outpath(os.join)

        outmatrix =  join (scratch, scriptfile) + ".matrix"
        #outmatrixparse =  join (scratch, scriptfile) + ".matrix.parse.txt"
        outmatrix2 =  scriptfile + ".matrix.txt"
        outjson =    scriptfile + ".matrix.parse.txt.json"



        computescript = join (rscripts, scriptfile)
        if (exists(computescript) == False):
                logger.info("Rscript does not exist")
                return False
        #Generate command to be executed
        ropts = ["Rscript", computescript]

        ropts.append("--cuffdiff_dir")
        ropts.append(cuffdiff_dir)

        ropts.append("--out")
        ropts.append(outmatrix)


        roptstr = " ".join(str(x) for x in ropts)

        #Run Rscript to generate Expression matrix
        openedprocess = subprocess.Popen (roptstr, shell=True, stdout=subprocess.PIPE)
        openedprocess.wait()

        if openedprocess.returncode !=0:
            logger.info("R script did not return normally, return code -"
                + str(openedprocess.returncode))
            return False

        matrix_parse = parse_expression_matrix_separate_comma(outmatrix)
        #convert expression matrix TSV to json

        cmd_expression_json = [TSV_to_FeatureValue,
                                    '--workspace_service_url', ws_url,
                                    '--workspace_name', workspace,
                                    '--object_name', matrix_parse,
                                    '--working_directory', scratch,
                                    '--input_directory', scratch,
                                    '--output_file_name', outjson ]

        cmd_expression_json = ["perl", '/kb/module/lib/kb_cummerbund/get_exp_matrix.pl', '/kb/module/work/outmatrix.parse.txt', '/kb/module/work/out.json'] 
        logger.info (" ".join(cmd_expression_json))
        tool_process = subprocess.Popen (" ".join (cmd_expression_json), stderr=subprocess.PIPE, shell=True)
        stdout, stderr = tool_process.communicate()

        if stdout is not None and len(stdout) > 0:
            logger.info(stdout)
        if stderr is not None and len(stderr) > 0:
            logger.info(stderr)

        if tool_process.returncode != 0:
           return False

        return outjson



def filter_expression_matrix(fparams, system_params):
    cuffdiff_dir=fparams['cuffdiff_dir']
    scratch = system_params['scratch']
    selected_condition_option = fparams['pairs']
    sample1 = fparams['sample1']
    sample2 = fparams['sample2']
    q_value_cutoff = abs(float(fparams['q_value_cutoff']))
    log2_fold_change_cutoff = abs(float(fparams['log2_fold_change_cutoff']))
    print q_value_cutoff
    print log2_fold_change_cutoff
    infile  =fparams['infile']
    outfile = fparams['outfile']
    num_genes = 1000000000000000000000 #no upper bound
    try:
        num_genes=int(fparams['num_genes'])
    except:
        num_genes = 100
    outf = f.filter_expresssion_matrix_option(scratch, infile,outfile,sample1, sample2, num_genes, q_value_cutoff, log2_fold_change_cutoff)
    if (os.path.isfile(outf)):
       return outf
    else:
       return False


def is_valid_row(selected_condition_option, sample1, sample2, sample1_name, sample2_name):

    #User selects 3 options None, All , pair.
    #If the user has selected None (0), no filtering based on sample is done
    #If the user has selected All (2), all pairwise options are taken into account
    #If ths uer has selecte pair (1), only one pair will be taken care of

    #return 1 if you want to consider the row for differential expression

     if (selected_condition_option==0):
         return 1
     if (selected_condition_option==2):
         return 1
     if (selected_condition_option==1):
            match=0
            if (sample1_name == sample1):
                match = match + 1
            if (sample2_name == sample1):
                match = match + 1
            if (sample1_name == sample2):
                match = match + 1
            if (sample2_name == sample2):
                match = match + 1
            if (match != 2):
               return 0
         
     return 1




def get_gene_list_from_filter_step(fparams):
        outfile = fparams['outfile']
        infile = fparams['infile']
        newlist = []
        fp=open(outfile, "w")

        with open(infile) as f:
                i=0
                for line in f:
                        i = i + 1
                        if (i==1):
                                continue
                        genes  = line.split("\t",1)[0]
                        genes = genes.strip('"') + "\n"
                        fp.write(genes)
                f.close()
                return outfile



def create_heatmap_from_genelist(fparams, system_params):
    cuffdiff_dir=fparams['cuffdiff_dir']
    sample1 = fparams['sample1']
    sample2 = fparams['sample2']
    q_value_cutoff = fparams['q_value_cutoff']
    #include_inf = fparams['include_inf']
    log2_fold_change_cutoff = fparams['log2_fold_change_cutoff']
    infile  =fparams['infile']
    num_genes = fparams['num_genes']
    infile = fparams['infile']
    outfile = fparams['outfile']
    outjson = fparams['outjson']

    logger=system_params['logger']

    #if exists(cuffdiff_dir) == False:
    #    logger.info("Cuffdiff directory does not exists")
    #return False
    if (num_genes > 500):
        num_genes = 500;

    fp=open(outfile, "w")
    x = "gene\tq_value\t_log2(fold_change)\n"
    fp.write(x)
    mylist = []
    with open(infile) as f:
        qval_dict={}
        i=0
        for line in f:
            linesplit  = line.split()
            qval = linesplit[12]
            if (qval =='q_value'):
                continue
            log2_fold_change = linesplit[9]

          #  if (include_inf==0):
          #  	if (log2_fold_change.find('inf') != -1 ):
          #  		continue
            #logger.info(log2_fold_change)

            gene = linesplit[2]
            sample1_name = linesplit[4]
            sample2_name = linesplit[5]
            match=0
            if (sample1_name == sample1):
                match = match + 1
            if (sample2_name == sample1):
                match = match + 1
            if (sample1_name == sample2):
                match = match + 1
            if (sample2_name == sample2):
                match = match + 1

            if (match != 2):
                continue
            if (float(qval) > q_value_cutoff):
                continue
            if (log2_fold_change.find('inf') == -1 ):
                if (abs(float(log2_fold_change)) < abs(float(log2_fold_change_cutoff))):
                    continue
            genes=gene.split(",");
            if (len(genes) >1):
                for j in genes:
                    x=[]
                    x.append(j)
                    x.append(str(qval))
                    x.append(str(log2_fold_change))
                    mylist.append(x)
            else:
                    x=[]
                    x.append(gene)
                    x.append(str(qval))
                    x.append(str(log2_fold_change))
                    mylist.append(x)
        mylistsorted = sorted(mylist, key=lambda line: abs(float(line[2])), reverse=True)
        j=0
        for x in mylistsorted:
            logger.info(x)
            j = j +1
            fp.write('{0}\n'.format('\t'.join(x)))
            if (j >= num_genes):
                break
        f.close()
        fp.close()
        return outfile



def upload_feature_value (system_params, fparams):
    logger      = system_params['logger']
    scratch     = system_params['scratch']
    shock_url   = system_params['shock_url']
    hs_url      = system_params['hs_url']
    ws_url      = system_params['ws_url']
    token       = system_params['token']
    workspace   = system_params['workspace']

    #cuffdiff_dir=fparams['cuffdiff_dir']
    #rscripts=fparams['rscripts']
    #sample1 = fparams['sample1']
    #sample2 = fparams['sample2']
    #q_value_cutoff = fparams['q_value_cutoff']
    #include_inf = fparams['include_inf']
    #log2_fold_change_cutoff = fparams['log2_fold_change_cutoff']
    #infile =fparams['infile']
    #num_genes = fparams['numgenes']


    #generate expression matrix
    #input = Rscript fpkmgenematrix.R cuffdiff_dir outpath(os.join)
    scriptfile = "tmp"
    cuffdiff_dir=fparams['cuffdiff_dir']

    infile =  join(cuffdiff_dir, "gene_exp.diff")
    outfile = "gene_exp.diff.filter.txt"
    outjson =  "gene_exp.diff.filter.json"

    fparams['infile'] = infile
    fparams['outfile'] = outfile
    fparams['outjson'] = outjson

    
    x = filter_expression_matrix(fparams, system_params)
    #infile,sample1, sample2, q_value_cutoff=0.05, include_inf=1, log2_fold_change_cutoff=2, num_genes=100)



    #matrix_parse = parse_expression_matrix_separate_comma(outmatrix)

    #convert expression matrix TSV to json
    TSV_to_FeatureValue = "trns_transform_TSV_Exspression_to_KBaseFeatureValues_ExpressionMatrix"
    returnVal = False

    cmd_expression_json = [TSV_to_FeatureValue,
                                '--workspace_service_url', ws_url,
                                '--workspace_name', workspace,
                                '--object_name', outfile,
                                '--working_directory', scratch,
                                '--input_directory', scratch,
                                '--output_file_name', outjson ]
    cmd_expression_json = ["perl", '/kb/module/lib/kb_cummerbund/get_exp_matrix.pl', '/kb/module/work/outmatrix.parse.txt', '/kb/module/work/out.json'] 
    logger.info (" ".join(cmd_expression_json))
    tool_process = subprocess.Popen (" ".join (cmd_expression_json), stderr=subprocess.PIPE, shell=True)
    stdout, stderr = tool_process.communicate()

    if stdout is not None and len(stdout) > 0:
        logger.info(stdout)
    if stderr is not None and len(stderr) > 0:
        logger.info(stderr)

    if tool_process.returncode != 0:
       return False

    return outjson

